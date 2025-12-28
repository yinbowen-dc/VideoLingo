import subprocess
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.config_utils import load_key
from rich import print as rprint
import time
import json
import librosa
import soundfile as sf
import tempfile
from core.all_whisper_methods.audio_preprocess import save_language

OUTPUT_LOG_DIR = "output/log"

def transcribe_audio_302(raw_audio_path: str, vocal_audio_path: str, start: float = None, end: float = None):
    os.makedirs(OUTPUT_LOG_DIR, exist_ok=True)
    LOG_FILE = f"{OUTPUT_LOG_DIR}/whisperx302.json"
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
        
    WHISPER_LANGUAGE = load_key("whisper.language")
    save_language(WHISPER_LANGUAGE)
    
    # 加载音频并处理start和end参数
    y, sr = librosa.load(vocal_audio_path, sr=16000)
    audio_duration = len(y) / sr
    
    if not start or not end:
        start = 0
        end = audio_duration
        
    start_sample = int(start * sr)
    end_sample = int(end * sr)
    y_slice = y[start_sample:end_sample]
    
    # 创建临时音频文件
    audio_file = "output/audio/raw.mp3"
    try:
        
        # 构建curl命令 - 完全模拟你成功的命令
        api_key = load_key("whisper.whisperX_302_api_key")
        
        curl_command = [
            'curl',
            '--proxy', 'http://127.0.0.1:7897',
            '-X', 'POST',
            '-H', f'Authorization: Bearer {api_key}',
            '-F', f'audio_input=@{audio_file}',
            '-F', f'processing_type=align',
            '-F', f'output=raw',
            '-F', f'language={WHISPER_LANGUAGE}',
            'https://api.302.ai/302/whisperx'
        ]
        
        start_time = time.time()
        rprint(f"[cyan]🎤 使用curl转录音频，语言: <{WHISPER_LANGUAGE}> ...[/cyan]")
        
        # 打印实际执行的命令（正确格式化）
        cmd_parts = []
        for arg in curl_command:
            if ' ' in arg or arg.startswith('Authorization:') or arg.startswith('Content-Type:'):
                cmd_parts.append(f'"{arg}"')
            else:
                cmd_parts.append(arg)
        cmd_str = ' '.join(cmd_parts)
        rprint(f"[yellow]执行命令: {cmd_str}[/yellow]")
        
        # 执行curl命令
        result = subprocess.run(
            curl_command,
            capture_output=True,
            text=True,
            timeout=180
        )
        print(result)
        if result.returncode != 0:
            rprint(f"[red]❌ curl命令失败 (返回码: {result.returncode})[/red]")
            rprint(f"[red]错误信息: {result.stderr}[/red]")
            if result.stdout:
                rprint(f"[yellow]输出信息: {result.stdout}[/yellow]")
            return None
        
        # 解析JSON响应
        try:
            response_json = json.loads(result.stdout)
            rprint(f"[green]✓ 成功获取响应[/green]")
            
            # 检查响应格式并转换为标准格式
            if 'segments' not in response_json and 'text' in response_json:
                # 如果是简单的whisper格式，转换为segments格式
                response_json = {
                    'segments': [{
                        'start': 0,
                        'end': audio_duration,
                        'text': response_json['text']
                    }],
                    'language': WHISPER_LANGUAGE
                }
            
            rprint(f"[green]✓ 成功获取 {len(response_json.get('segments', []))} 个片段[/green]")
            
        except json.JSONDecodeError as e:
            rprint(f"[red]❌ JSON解析失败: {e}[/red]")
            rprint(f"[yellow]原始响应: {result.stdout[:500]}...[/yellow]")
            return None
        
    except subprocess.TimeoutExpired:
        rprint(f"[red]❌ 请求超时[/red]")
        return None
    except Exception as e:
        rprint(f"[red]❌ 执行失败: {e}[/red]")
        return None
    
    # 调整时间戳
    if start is not None and start > 0:
        for segment in response_json.get('segments', []):
            segment['start'] += start
            segment['end'] += start
            for word in segment.get('words', []):
                if 'start' in word:
                    word['start'] += start
                if 'end' in word:
                    word['end'] += start
    
    # 保存调整后的结果
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(response_json, f, indent=4, ensure_ascii=False)
    
    elapsed_time = time.time() - start_time
    rprint(f"[green]✓ 转录完成，耗时 {elapsed_time:.2f} 秒[/green]")
    return response_json

if __name__ == "__main__":  
    # 使用示例:
    result = transcribe_audio_302("output/audio/raw.mp3", "output/audio/raw.mp3")
    if result:
        rprint(f"[green]成功！获得 {len(result.get('segments', []))} 个片段[/green]")
        # 打印第一个片段的内容
        if result.get('segments'):
            rprint(f"[cyan]第一个片段: {result['segments'][0].get('text', 'N/A')}[/cyan]")
    else:
        rprint("[red]失败！[/red]")