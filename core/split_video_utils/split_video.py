#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import argparse
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint
from rich.prompt import Confirm

# 创建控制台对象
console = Console()

def format_time(seconds):
    """格式化时间显示"""
    if seconds < 0:
        return "0:00.000"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:06.3f}"
    else:
        return f"{minutes}:{secs:06.3f}"

def get_video_duration(video_path):
    """获取视频时长"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            info = json.loads(result.stdout)
            duration = float(info['format']['duration'])
            return duration
        else:
            rprint(f"[red]❌ 获取视频时长失败[/red]")
            return None
            
    except Exception as e:
        rprint(f"[red]❌ 获取视频时长错误: {e}[/red]")
        return None

def check_demucs_installation():
    """检查Demucs是否安装"""
    try:
        result = subprocess.run(['python', '-c', 'import demucs'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except:
        return False

def extract_video_segment(input_path, start_time, duration, output_path):
    """提取视频片段"""
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-c', 'copy',
        output_path,
        '-y'
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return True
    except Exception as e:
        rprint(f"[red]❌ 视频片段提取失败: {e}[/red]")
        return False

def extract_audio_from_video(video_path, output_audio_path):
    """从视频中提取音频"""
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vn',
        '-acodec', 'libmp3lame',
        '-ab', '192k',
        '-ar', '44100',
        output_audio_path,
        '-y'
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        return True
    except Exception as e:
        rprint(f"[red]❌ 音频提取失败: {e}[/red]")
        return False
def separate_vocals_with_demucs(audio_path, output_dir):
    """使用Demucs分离人声"""
    try:
        # 检查输入文件
        if not os.path.exists(audio_path):
            rprint(f"[red]❌ 音频文件不存在: {audio_path}[/red]")
            return None
        
        file_size = os.path.getsize(audio_path)
        rprint(f"[cyan]  📁 音频文件: {os.path.basename(audio_path)} ({file_size/1024:.1f}KB)[/cyan]")
        
        # 创建临时目录
        temp_dir = os.path.join(output_dir, "demucs_temp")
        os.makedirs(temp_dir, exist_ok=True)
        rprint(f"[cyan]  📂 临时目录: {temp_dir}[/cyan]")
        
        # 运行Demucs
        cmd = [
            'python', '-m', 'demucs.separate',
            '--two-stems=vocals',
            '-o', temp_dir,
            audio_path
        ]
        
        rprint(f"[cyan]  🎤 开始分离人声...[/cyan]")
        rprint(f"[dim]  命令: {' '.join(cmd)}[/dim]")
        
        with console.status("[yellow]🎤 分离人声中...", spinner="dots"):
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        rprint(f"[cyan]  📊 Demucs返回码: {result.returncode}[/cyan]")
        
        if result.returncode != 0:
            rprint(f"[red]❌ Demucs执行失败[/red]")
            rprint(f"[red]stderr: {result.stderr}[/red]")
            rprint(f"[red]stdout: {result.stdout}[/red]")
            return None
        
        # 查找输出文件
        audio_name = os.path.splitext(os.path.basename(audio_path))[0]
        rprint(f"[cyan]  🔍 查找输出文件，音频名: {audio_name}[/cyan]")
        
        vocals_path = None
        all_files = []
        
        # 搜索输出文件
        for root, dirs, files in os.walk(temp_dir):
            rprint(f"[dim]  搜索目录: {root}[/dim]")
            for file in files:
                full_path = os.path.join(root, file)
                all_files.append(full_path)
                rprint(f"[dim]    文件: {file}[/dim]")
                
                if 'vocals' in file.lower() and audio_name in file:
                    vocals_path = full_path
                    rprint(f"[green]  ✓ 找到人声文件: {file}[/green]")
                    break
        
        if not vocals_path:
            rprint(f"[yellow]⚠️ 未找到匹配的人声文件[/yellow]")
            rprint(f"[yellow]期望包含: 'vocals' 和 '{audio_name}'[/yellow]")
            rprint(f"[yellow]所有文件:[/yellow]")
            for f in all_files:
                rprint(f"[dim]  - {f}[/dim]")
            
            # 尝试查找任何包含vocals的文件
            for f in all_files:
                if 'vocals' in os.path.basename(f).lower():
                    vocals_path = f
                    rprint(f"[yellow]  🔄 使用备选文件: {os.path.basename(f)}[/yellow]")
                    break
        
        if not vocals_path:
            rprint(f"[red]❌ 完全找不到人声文件[/red]")
            return None
        
        # 检查找到的文件
        if not os.path.exists(vocals_path):
            rprint(f"[red]❌ 人声文件不存在: {vocals_path}[/red]")
            return None
        
        vocals_size = os.path.getsize(vocals_path)
        rprint(f"[green]  ✓ 人声文件大小: {vocals_size/1024:.1f}KB[/green]")
        
        if vocals_size < 1024:  # 小于1KB可能是空文件
            rprint(f"[yellow]⚠️ 人声文件太小，可能分离失败[/yellow]")
        
        # 移动到输出目录
        final_vocals_path = os.path.join(output_dir, f"{audio_name}_vocals.mp3")
        rprint(f"[cyan]  📁 目标路径: {final_vocals_path}[/cyan]")
        
        # 转换为mp3格式
        if vocals_path.endswith('.wav'):
            rprint(f"[cyan]  🔄 转换WAV到MP3[/cyan]")
            convert_cmd = [
                'ffmpeg', '-i', vocals_path, 
                '-acodec', 'libmp3lame', 
                '-ab', '192k',
                final_vocals_path, '-y'
            ]
            convert_result = subprocess.run(convert_cmd, capture_output=True, text=True, timeout=60)
            
            if convert_result.returncode != 0:
                rprint(f"[red]❌ 格式转换失败[/red]")
                rprint(f"[red]stderr: {convert_result.stderr}[/red]")
                return None
        else:
            rprint(f"[cyan]  📋 复制文件[/cyan]")
            import shutil
            shutil.copy2(vocals_path, final_vocals_path)
        
        # 验证最终文件
        if os.path.exists(final_vocals_path):
            final_size = os.path.getsize(final_vocals_path)
            rprint(f"[green]  ✅ 人声分离完成: {os.path.basename(final_vocals_path)} ({final_size/1024:.1f}KB)[/green]")
            
            # 清理临时目录
            try:
                import shutil
                shutil.rmtree(temp_dir)
                rprint(f"[dim]  🧹 清理临时目录[/dim]")
            except:
                pass
            
            return final_vocals_path
        else:
            rprint(f"[red]❌ 最终文件创建失败[/red]")
            return None
            
    except subprocess.TimeoutExpired:
        rprint(f"[red]❌ Demucs执行超时 (>300秒)[/red]")
        return None
    except Exception as e:
        rprint(f"[red]❌ 人声分离错误: {e}[/red]")
        import traceback
        rprint(f"[red]详细错误: {traceback.format_exc()}[/red]")
        return None

def detect_speech_pauses_in_segment(vocals_path):
    """检测音频片段中的人声停顿"""
    speech_configs = [
        (-15, 0.05, "词间停顿(-15dB, 50ms)", "词间"),
        (-18, 0.05, "短句停顿(-18dB, 50ms)", "短句"),
        (-20, 0.05, "句间停顿(-20dB, 50ms)", "句间"),
        (-25, 0.05, "段落停顿(-25dB, 50ms)", "段落"),
        (-15, 0.1, "词间停顿(-15dB, 100ms)", "词间"),
        (-18, 0.1, "短句停顿(-18dB, 100ms)", "短句"),
        (-20, 0.1, "句间停顿(-20dB, 100ms)", "句间"),
        (-25, 0.1, "段落停顿(-25dB, 100ms)", "段落"),
        (-15, 0.15, "长词间(-15dB, 150ms)", "长词间"),
        (-18, 0.15, "长句间(-18dB, 150ms)", "长句间"),
        (-20, 0.15, "自然停顿(-20dB, 150ms)", "自然"),
    ]
    
    all_results = []
    
    for noise_db, min_duration, desc, pause_type in speech_configs:
        cmd = [
            'ffmpeg',
            '-i', vocals_path,
            '-af', f'silencedetect=noise={noise_db}dB:duration={min_duration}',
            '-f', 'null',
            '-',
            '-v', 'info'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            silence_periods = []
            current_silence_start = None
            
            for line in result.stderr.split('\n'):
                line = line.strip()
                
                if 'silence_start:' in line:
                    try:
                        start_part = line.split('silence_start:')[1].strip()
                        silence_start = float(start_part.split()[0])
                        current_silence_start = silence_start
                    except:
                        continue
                        
                elif 'silence_end:' in line and current_silence_start is not None:
                    try:
                        parts = line.split('silence_end:')[1]
                        
                        if '|' in parts:
                            end_part = parts.split('|')[0].strip()
                            duration_part = parts.split('silence_duration:')[1].strip()
                            silence_end = float(end_part)
                            silence_duration = float(duration_part)
                        else:
                            silence_end = float(parts.strip())
                            silence_duration = silence_end - current_silence_start
                        
                        if silence_duration >= min_duration:
                            silence_periods.append({
                                'start': current_silence_start,
                                'end': silence_end,
                                'duration': silence_duration,
                                'center': (current_silence_start + silence_end) / 2,
                                'type': pause_type
                            })
                        current_silence_start = None
                    except:
                        continue
            
            # 按停顿时长分类
            micro_pauses = [s for s in silence_periods if 0.05 <= s['duration'] < 0.1]
            short_pauses = [s for s in silence_periods if 0.1 <= s['duration'] < 0.2]
            medium_pauses = [s for s in silence_periods if 0.2 <= s['duration'] < 0.5]
            long_pauses = [s for s in silence_periods if s['duration'] >= 0.5]
            
            result_info = {
                'config': (noise_db, min_duration, desc, pause_type),
                'silences': silence_periods,
                'count': len(silence_periods),
                'micro': len(micro_pauses),
                'short': len(short_pauses),
                'medium': len(medium_pauses),
                'long': len(long_pauses)
            }
            all_results.append(result_info)
                
        except Exception as e:
            continue
    
    return all_results

# ==================== 主要功能函数 ====================
def generate_cut_plan(input_video_path, output_dir, target_interval=30):
    """
    函数1: 生成切分计划
    输入长视频，每隔30分钟进行切分检测，输出执行计划
    """
    rprint(Panel.fit("[bold magenta]🎯 生成智能切分计划[/bold magenta]", border_style="magenta"))
    
    # 检查文件和环境
    if not os.path.exists(input_video_path):
        rprint(f"[bold red]❌ 文件不存在: {input_video_path}[/bold red]")
        return None
    
    if not check_demucs_installation():
        rprint("[red]❌ Demucs未安装，请运行: pip install demucs[/red]")
        return None
    
    # 获取视频信息
    total_duration = get_video_duration(input_video_path)
    if total_duration is None:
        return None
    
    rprint(f"[green]✓ 视频文件[/green]: [cyan]{os.path.basename(input_video_path)}[/cyan]")
    rprint(f"[green]✓ 视频时长[/green]: [yellow]{format_time(total_duration)}[/yellow]")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 💾 定义保存文件路径
    progress_file = os.path.join(output_dir, "cut_progress.json")
    plan_file = os.path.join(output_dir, "cut_plan.json")
    
    # 计算检测点
    interval_seconds = target_interval * 60
    detection_points = []
    
    current_time = interval_seconds
    while current_time < total_duration:
        detection_points.append(current_time)
        current_time += interval_seconds
    
    if not detection_points:
        rprint(f"[yellow]⚠️ 视频时长不足{target_interval}分钟，无需切分[/yellow]")
        # 返回单段计划
        plan = {
            'input_video': input_video_path,
            'total_duration': total_duration,
            'target_interval': target_interval,
            'cut_points': [],
            'segments': [{
                'index': 1,
                'start': 0,
                'end': total_duration,
                'duration': total_duration,
                'cut_type': 'whole'
            }]
        }
        return plan
    
    # 🔄 检查是否有已保存的进度
    cut_points = []
    start_index = 0
    
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            
            # 验证进度文件是否匹配当前任务
            if (progress_data.get('input_video') == input_video_path and 
                abs(progress_data.get('total_duration', 0) - total_duration) < 1):
                
                cut_points = progress_data.get('completed_cut_points', [])
                start_index = len(cut_points)
                
                if start_index > 0:
                    rprint(f"[green]🔄 发现已有进度: 已完成 {start_index}/{len(detection_points)} 个切分点[/green]")
                    for point in cut_points:
                        rprint(f"[dim]  ✓ {format_time(point['target'])} -> {format_time(point['actual'])}[/dim]")
        except:
            rprint(f"[yellow]⚠️ 无法加载进度文件，重新开始[/yellow]")
    
    rprint(f"[cyan]📍 计划检测 {len(detection_points)} 个切分点[/cyan]")
    
    # 对每个检测点进行分析
    try:
        for i, target_time in enumerate(detection_points):
            # 跳过已完成的点
            if i < start_index:
                continue
                
            rprint(f"\n[yellow]🎯 分析切分点 {i+1}/{len(detection_points)} (目标: {format_time(target_time)})[/yellow]")
            
            cut_point = detect_optimal_cut_point(
                input_video_path, 
                target_time, 
                total_duration, 
                output_dir, 
                i+1
            )
            
            if cut_point:
                cut_points.append(cut_point)
                rprint(f"[green]✅ 找到切分点: {format_time(cut_point['actual'])} (偏差: {cut_point['deviation']:+.1f}s)[/green]")
            else:
                # 使用备选点
                fallback_point = {
                    'target': target_time,
                    'actual': target_time,
                    'deviation': 0,
                    'silence_duration': 0,
                    'silence_type': 'fallback',
                    'confidence': 'low'
                }
                cut_points.append(fallback_point)
                rprint(f"[yellow]⚠️ 使用备选点: {format_time(target_time)}[/yellow]")
            
            # 💾 每完成一个点就保存进度
            try:
                progress_data = {
                    'input_video': input_video_path,
                    'total_duration': total_duration,
                    'target_interval': target_interval,
                    'completed_cut_points': cut_points,
                    'progress': f"{len(cut_points)}/{len(detection_points)}"
                }
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress_data, f, ensure_ascii=False, indent=2)
                rprint(f"[dim]💾 进度已保存 ({len(cut_points)}/{len(detection_points)})[/dim]")
            except:
                pass
    
    except KeyboardInterrupt:
        rprint(f"\n[yellow]⚠️ 用户中断，进度已保存，可重新运行继续[/yellow]")
        return None
    
    # 生成段落信息
    segments = []
    
    # 第一段：从开始到第一个切分点
    if cut_points:
        segments.append({
            'index': 1,
            'start': 0,
            'end': cut_points[0]['actual'],
            'duration': cut_points[0]['actual'],
            'cut_type': 'start'
        })
        
        # 中间段落
        for i in range(len(cut_points) - 1):
            segments.append({
                'index': i + 2,
                'start': cut_points[i]['actual'],
                'end': cut_points[i + 1]['actual'],
                'duration': cut_points[i + 1]['actual'] - cut_points[i]['actual'],
                'cut_type': 'middle'
            })
        
        # 最后一段：从最后一个切分点到结束
        segments.append({
            'index': len(cut_points) + 1,
            'start': cut_points[-1]['actual'],
            'end': total_duration,
            'duration': total_duration - cut_points[-1]['actual'],
            'cut_type': 'end'
        })
    
    # 创建切分计划
    plan = {
        'input_video': input_video_path,
        'total_duration': total_duration,
        'target_interval': target_interval,
        'cut_points': cut_points,
        'segments': segments
    }
    
    # 保存计划到文件
    with open(plan_file, 'w', encoding='utf-8') as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    
    rprint(f"[green]✓ 切分计划已保存: {plan_file}[/green]")
    
    # 🧹 完成后清理进度文件
    try:
        if os.path.exists(progress_file):
            os.remove(progress_file)
    except:
        pass
    
    return plan

def detect_optimal_cut_point(input_video_path, target_time, total_duration, output_dir, point_index):
    """
    函数2: 切分检测函数 (简化版)
    在指定时间点附近检测最佳切分位置
    - 使用30秒分析窗口
    - 只检测-25dB以下的静音
    - 选择窗口内最后一个静音点作为切分点
    """
    # 定义分析窗口：目标时间前后各30秒
    window_size = 30  # 30秒
    start_time = max(0, target_time - window_size)
    end_time = min(total_duration, target_time + window_size)
    analysis_duration = end_time - start_time
    
    rprint(f"[cyan]  📊 分析窗口: {format_time(start_time)} - {format_time(end_time)} (±{window_size}s)[/cyan]")
    
    # 提取分析片段
    segment_path = os.path.join(output_dir, f"temp_segment_{point_index}.mp4")
    if not extract_video_segment(input_video_path, start_time, analysis_duration, segment_path):
        rprint(f"[yellow]  ⚠️ 提取片段失败，使用目标时间[/yellow]")
        return {
            'target': target_time,
            'actual': target_time,
            'deviation': 0,
            'silence_duration': 0,
            'silence_type': 'fallback',
            'confidence': 'low',
            'reason': 'extract_failed'
        }
    
    # 提取音频
    audio_path = os.path.join(output_dir, f"temp_audio_{point_index}.mp3")
    if not extract_audio_from_video(segment_path, audio_path):
        rprint(f"[yellow]  ⚠️ 提取音频失败，使用目标时间[/yellow]")
        if os.path.exists(segment_path):
            os.remove(segment_path)
        return {
            'target': target_time,
            'actual': target_time,
            'deviation': 0,
            'silence_duration': 0,
            'silence_type': 'fallback',
            'confidence': 'low',
            'reason': 'audio_failed'
        }
    
    # 分离人声
    vocals_path = separate_vocals_with_demucs(audio_path, output_dir)
    if not vocals_path:
        rprint(f"[yellow]  ⚠️ 人声分离失败，使用目标时间[/yellow]")
        for temp_file in [segment_path, audio_path]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        return {
            'target': target_time,
            'actual': target_time,
            'deviation': 0,
            'silence_duration': 0,
            'silence_type': 'fallback',
            'confidence': 'low',
            'reason': 'vocals_failed'
        }
    
    # 检测30秒窗口内的所有静音段：-25dB，最小时长50ms
    rprint(f"[cyan]  🔍 检测30秒窗口内的静音段 (-25dB, ≥50ms)[/cyan]")
    
    cmd = [
        'ffmpeg',
        '-i', vocals_path,
        '-af', 'silencedetect=noise=-25dB:duration=0.05',
        '-f', 'null',
        '-',
        '-v', 'info'
    ]
    
    silences = []
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        current_silence_start = None
        
        for line in result.stderr.split('\n'):
            line = line.strip()
            
            # 解析 silence_start
            if 'silence_start:' in line:
                try:
                    start_part = line.split('silence_start:')[1].strip()
                    silence_start = float(start_part.split()[0])
                    current_silence_start = silence_start
                except Exception:
                    continue
            
            # 解析 silence_end
            elif 'silence_end:' in line and current_silence_start is not None:
                try:
                    parts = line.split('silence_end:')[1]
                    
                    if '|' in parts:
                        end_part = parts.split('|')[0].strip()
                        duration_part = parts.split('silence_duration:')[1].strip()
                        silence_end = float(end_part)
                        silence_duration = float(duration_part)
                    else:
                        silence_end = float(parts.strip())
                        silence_duration = silence_end - current_silence_start
                    
                    if silence_duration >= 0.05:  # 至少50ms
                        silences.append({
                            'start': current_silence_start,
                            'end': silence_end,
                            'duration': silence_duration,
                            'center': (current_silence_start + silence_end) / 2,
                            'absolute_center': start_time + (current_silence_start + silence_end) / 2,
                            'type': 'detected'
                        })
                    
                    current_silence_start = None
                    
                except Exception:
                    continue
        
    except Exception as e:
        rprint(f"[red]  ❌ 静音检测失败: {e}[/red]")
        silences = []
    
    if not silences:
        rprint(f"[yellow]  ⚠️ 未检测到静音段，使用目标时间[/yellow]")
        # 清理临时文件
        for temp_file in [segment_path, audio_path, vocals_path]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        return {
            'target': target_time,
            'actual': target_time,
            'deviation': 0,
            'silence_duration': 0,
            'silence_type': 'fallback',
            'confidence': 'low',
            'reason': 'no_silences'
        }
    
    rprint(f"[green]  ✓ 检测到 {len(silences)} 个静音段[/green]")
    
    # 显示所有静音段的信息
    for i, silence in enumerate(silences):
        rprint(f"    {i+1}. {format_time(silence['absolute_center'])} (时长: {silence['duration']*1000:.0f}ms)")
    
    # 选择最后一个静音段作为切分点
    last_silence = silences[-1]
    absolute_time = last_silence['absolute_center']
    
    best_candidate = {
        'target': target_time,
        'actual': absolute_time,
        'deviation': absolute_time - target_time,
        'silence_duration': last_silence['duration'],
        'silence_type': last_silence['type'],
        'confidence': 'high',
        'strategy': 'last_silence',
        'total_silences': len(silences)
    }
    
    # 清理临时文件
    for temp_file in [segment_path, audio_path, vocals_path]:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    # 输出结果
    rprint(f"[green]  ✅ 选择最后一个静音段: {format_time(absolute_time)} | "
          f"偏差: {best_candidate['deviation']:+.1f}s | "
          f"静音: {best_candidate['silence_duration']*1000:.0f}ms | "
          f"总静音段: {len(silences)}个[/green]")
    
    return best_candidate

def execute_cut_plan(plan, output_dir):
    """
    函数3: 执行切分计划
    根据切分计划实际切分视频
    """
    rprint(Panel.fit("[bold green]🚀 执行视频切分[/bold green]", border_style="green"))
    
    input_video = plan['input_video']
    segments = plan['segments']
    
    if not os.path.exists(input_video):
        rprint(f"[red]❌ 源视频文件不存在: {input_video}[/red]")
        return False
    
    # 创建输出目录
    segments_dir = os.path.join(output_dir, "segments")
    os.makedirs(segments_dir, exist_ok=True)
    
    rprint(f"[cyan]📁 输出目录: {segments_dir}[/cyan]")
    rprint(f"[cyan]🎬 开始切分 {len(segments)} 个片段...[/cyan]")
    
    success_count = 0
    
    for segment in segments:
        segment_name = f"segment_{segment['index']:02d}.mp4"
        output_path = os.path.join(segments_dir, segment_name)
        
        rprint(f"\n[yellow]✂️ 切分片段 {segment['index']}: {format_time(segment['start'])} - {format_time(segment['end'])}[/yellow]")
        
        cmd = [
            'ffmpeg',
            '-i', input_video,
            '-ss', str(segment['start']),
            '-t', str(segment['duration']),
            '-c', 'copy',
            output_path,
            '-y'
        ]
        
        try:
            with console.status(f"[yellow]处理片段 {segment['index']}...", spinner="dots"):
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                file_size = os.path.getsize(output_path) / 1024 / 1024  # MB
                rprint(f"[green]✅ 片段 {segment['index']} 完成: {segment_name} ({file_size:.1f}MB)[/green]")
                success_count += 1
            else:
                rprint(f"[red]❌ 片段 {segment['index']} 失败: {result.stderr}[/red]")
                
        except subprocess.TimeoutExpired:
            rprint(f"[red]❌ 片段 {segment['index']} 超时[/red]")
        except Exception as e:
            rprint(f"[red]❌ 片段 {segment['index']} 错误: {e}[/red]")
    
    # 生成切分报告
    report_file = os.path.join(output_dir, "cut_report.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("视频切分报告\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"源视频: {os.path.basename(input_video)}\n")
        f.write(f"总时长: {format_time(plan['total_duration'])}\n")
        f.write(f"目标间隔: {plan['target_interval']} 分钟\n")
        f.write(f"切分点数: {len(plan['cut_points'])}\n")
        f.write(f"生成片段: {len(segments)}\n")
        f.write(f"成功片段: {success_count}\n")
        f.write(f"成功率: {success_count/len(segments)*100:.1f}%\n\n")
        
        f.write("片段详情:\n")
        f.write("-" * 30 + "\n")
        for segment in segments:
            f.write(f"片段 {segment['index']:2d}: {format_time(segment['start'])} - {format_time(segment['end'])} ({format_time(segment['duration'])})\n")
    
    rprint(f"\n[green]🎉 切分完成! 成功: {success_count}/{len(segments)}[/green]")
    rprint(f"[cyan]📋 报告已保存: {report_file}[/cyan]")
    
    return success_count == len(segments)

def display_cut_plan(plan):
    """显示切分计划的详细信息"""
    rprint(Panel.fit("[bold blue]📋 切分计划预览[/bold blue]", border_style="blue"))
    
    # 基本信息
    rprint(f"[green]📁 源视频[/green]: {os.path.basename(plan['input_video'])}")
    rprint(f"[green]⏱️ 总时长[/green]: {format_time(plan['total_duration'])}")
    rprint(f"[green]🎯 目标间隔[/green]: {plan['target_interval']} 分钟")
    rprint(f"[green]✂️ 切分点[/green]: {len(plan['cut_points'])} 个")
    rprint(f"[green]📹 生成片段[/green]: {len(plan['segments'])} 个")
    
    # 切分点详情
    if plan['cut_points']:
        rprint(f"\n[cyan]🎯 切分点详情:[/cyan]")
        for i, cp in enumerate(plan['cut_points']):
            confidence_color = "green" if cp.get('confidence') == 'high' else "yellow" if cp.get('confidence') == 'medium' else "red"
            rprint(f"  {i+1}. {format_time(cp['actual'])} (偏差: {cp['deviation']:+.1f}s, 类型: {cp['silence_type']}, 置信度: [{confidence_color}]{cp.get('confidence', 'unknown')}[/{confidence_color}])")
    
    # 段落预览表格
    rprint(f"\n[cyan]📹 段落预览:[/cyan]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("片段", style="dim", width=6)
    table.add_column("开始时间", style="cyan")
    table.add_column("结束时间", style="cyan")
    table.add_column("时长", style="yellow")
    table.add_column("类型", style="green")
    
    for segment in plan['segments']:
        table.add_row(
            f"{segment['index']:02d}",
            format_time(segment['start']),
            format_time(segment['end']),
            format_time(segment['duration']),
            segment['cut_type']
        )
    
    console.print(table)

def main():
    """主函数：组装调用逻辑"""
    parser = argparse.ArgumentParser(description="智能视频切分工具")
    parser.add_argument("--input", "-i", required=True, help="输入视频文件")
    parser.add_argument("--output", "-o", required=True, help="输出目录")
    parser.add_argument("--interval", "-t", type=int, default=30, help="目标切分间隔（分钟）")
    parser.add_argument("--auto", "-a", action="store_true", help="自动执行，不询问确认")
    
    args = parser.parse_args()
    
    # 步骤1: 生成切分计划
    rprint("[bold cyan]步骤 1/3: 生成切分计划[/bold cyan]")
    plan = generate_cut_plan(args.input, args.output, args.interval)
    
    if not plan:
        rprint("[red]❌ 生成切分计划失败[/red]")
        return
    
    # 步骤2: 显示计划并确认
    rprint(f"\n[bold cyan]步骤 2/3: 预览切分计划[/bold cyan]")
    display_cut_plan(plan)
    
    # 询问用户确认
    if not args.auto:
        if not Confirm.ask("\n[bold yellow]是否确认执行切分计划?[/bold yellow]"):
            rprint("[yellow]❌ 用户取消操作[/yellow]")
            return
    
    # 步骤3: 执行切分
    rprint(f"\n[bold cyan]步骤 3/3: 执行视频切分[/bold cyan]")
    success = execute_cut_plan(plan, args.output)
    
    if success:
        rprint(Panel(
            "[bold green]🎉 视频切分完成！[/bold green]\n\n"
            f"• 源视频: {os.path.basename(plan['input_video'])}\n"
            f"• 生成片段: {len(plan['segments'])} 个\n"
            f"• 输出目录: {args.output}/segments\n"
            f"• 切分报告: {args.output}/cut_report.txt",
            title="✨ 完成",
            border_style="green"
        ))
    else:
        rprint("[red]❌ 视频切分过程中出现错误[/red]")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        # 直接调用示例
        input_video = "/Users/luogaiyu/code/VideoLingo/videos/Learn Solidity Smart Contract Development ｜ Full 2024 Cyfrin Updraft Course.webm"
        output_directory = "/Users/luogaiyu/code/VideoLingo/output/smart_cut_test"
        
        # 步骤1: 生成切分计划
        rprint("[bold cyan]步骤 1/3: 生成切分计划[/bold cyan]")
        plan = generate_cut_plan(input_video, output_directory, target_interval=30)
        
        if plan:
            # 步骤2: 显示计划
            rprint(f"\n[bold cyan]步骤 2/3: 预览切分计划[/bold cyan]")
            display_cut_plan(plan)
            
            # 步骤3: 询问确认并执行
            if Confirm.ask("\n[bold yellow]是否确认执行切分计划?[/bold yellow]"):
                rprint(f"\n[bold cyan]步骤 3/3: 执行视频切分[/bold cyan]")
                execute_cut_plan(plan, output_directory)
            else:
                rprint("[yellow]用户取消操作[/yellow]")