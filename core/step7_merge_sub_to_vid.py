import os, subprocess, time, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config_utils import load_key
from core.step1_ytdlp import find_video_files
from rich import print as rprint
import cv2
import numpy as np
import platform

SRC_FONT_SIZE = 15
TRANS_FONT_SIZE = 17
FONT_NAME = 'Arial'
TRANS_FONT_NAME = 'Arial'

# Linux need to install google noto fonts: apt-get install fonts-noto
if platform.system() == 'Linux':
    FONT_NAME = 'NotoSansCJK-Regular'
    TRANS_FONT_NAME = 'NotoSansCJK-Regular'
# Mac OS has different font names
elif platform.system() == 'Darwin':
    FONT_NAME = 'Arial Unicode MS'
    TRANS_FONT_NAME = 'Arial Unicode MS'

SRC_FONT_COLOR = '&HFFFFFF'
SRC_OUTLINE_COLOR = '&H000000'
SRC_OUTLINE_WIDTH = 1
SRC_SHADOW_COLOR = '&H80000000'
TRANS_FONT_COLOR = '&H00FFFF'
TRANS_OUTLINE_COLOR = '&H000000'
TRANS_OUTLINE_WIDTH = 1 
TRANS_BACK_COLOR = '&H33000000'

OUTPUT_DIR = "output"
OUTPUT_VIDEO = f"{OUTPUT_DIR}/output_sub.mp4"
SRC_SRT = f"{OUTPUT_DIR}/src.srt"
TRANS_SRT = f"{OUTPUT_DIR}/trans.srt"
    
def check_gpu_available():
    # 当前gpu
    # try:
    #     result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
    #     return 'h264_nvenc' in result.stdout
    # except:
        return False

def merge_subtitles_to_video(test_mode=False, test_duration=30):
    """
    合并字幕到视频
    
    Args:
        test_mode (bool): 是否为测试模式，默认False
        test_duration (int): 测试模式下的时长（秒），默认30秒
    """
    video_file = find_video_files()
    
    # 🔥 根据模式决定输出文件
    if test_mode:
        output_video = f"{OUTPUT_DIR}/output_sub_test_{test_duration}s.mp4"
        rprint(f"[bold yellow]🧪 测试模式：只处理前{test_duration}秒[/bold yellow]")
    else:
        output_video = OUTPUT_VIDEO
        rprint("[bold blue]📹 正式模式：处理完整视频[/bold blue]")
    
    os.makedirs(os.path.dirname(output_video), exist_ok=True)

    # Check resolution
    if not load_key("burn_subtitles"):
        rprint("[bold yellow]Warning: A 0-second black video will be generated as a placeholder as subtitles are not burned in.[/bold yellow]")

        # Create a black frame
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_video, fourcc, 1, (1920, 1080))
        out.write(frame)
        out.release()

        rprint("[bold green]Placeholder video has been generated.[/bold green]")
        return

    if not os.path.exists(SRC_SRT) or not os.path.exists(TRANS_SRT):
        print("Subtitle files not found in the 'output' directory.")
        exit(1)

    video = cv2.VideoCapture(video_file)
    TARGET_WIDTH = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    TARGET_HEIGHT = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video.release()
    rprint(f"[bold green]Video resolution: {TARGET_WIDTH}x{TARGET_HEIGHT}[/bold green]")
    
    # 🔥 修复AV1问题和文件兼容性的FFmpeg命令
    ffmpeg_cmd = [
        'ffmpeg',
        '-y',                      # 🔥 强制覆盖输出文件
        '-hwaccel', 'none',        # 禁用硬件加速，解决AV1问题
        '-fflags', '+genpts',      # 生成时间戳
        '-avoid_negative_ts', 'make_zero',  # 避免时间戳问题
        '-i', video_file,
    ]
    
    # 🔥 如果是测试模式，添加时长限制
    if test_mode:
        ffmpeg_cmd.extend(['-t', str(test_duration)])
    
    # 添加视频滤镜
    ffmpeg_cmd.extend([
        '-vf', (
            f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
            f"subtitles={SRC_SRT}:force_style='FontSize={SRC_FONT_SIZE},FontName={FONT_NAME}," 
            f"PrimaryColour={SRC_FONT_COLOR},OutlineColour={SRC_OUTLINE_COLOR},OutlineWidth={SRC_OUTLINE_WIDTH},"
            f"ShadowColour={SRC_SHADOW_COLOR},BorderStyle=1',"
            f"subtitles={TRANS_SRT}:force_style='FontSize={TRANS_FONT_SIZE},FontName={TRANS_FONT_NAME},"
            f"PrimaryColour={TRANS_FONT_COLOR},OutlineColour={TRANS_OUTLINE_COLOR},OutlineWidth={TRANS_OUTLINE_WIDTH},"
            f"BackColour={TRANS_BACK_COLOR},Alignment=2,MarginV=27,BorderStyle=4'"
        ),
    ])

    # GPU检测和编码设置
    gpu_available = check_gpu_available()
    if gpu_available and not test_mode:  # 测试模式使用CPU更稳定
        rprint("[bold green]NVIDIA GPU encoder detected, will use GPU acceleration.[/bold green]")
        ffmpeg_cmd.extend(['-c:v', 'h264_nvenc'])
    else:
        rprint("[bold yellow]No NVIDIA GPU encoder detected, will use CPU instead.[/bold yellow]")
        ffmpeg_cmd.extend(['-c:v', 'libx264'])
        if test_mode:
            ffmpeg_cmd.extend(['-preset', 'fast'])  # 测试模式使用快速编码
        else:
            ffmpeg_cmd.extend(['-preset', 'medium'])  # 正式模式使用平衡编码
    
    # 🔥 修复文件兼容性问题
    ffmpeg_cmd.extend([
        '-pix_fmt', 'yuv420p',     # 🔥 确保像素格式兼容性
        '-c:a', 'aac',             # 🔥 重新编码音频为AAC确保兼容性
        '-b:a', '128k',            # 音频比特率
        '-movflags', '+faststart', # 🔥 优化MP4文件结构，便于播放
        output_video
    ])

    mode_text = f"前{test_duration}秒测试" if test_mode else "完整视频"
    print(f"🎬 开始处理{mode_text}...")
    start_time = time.time()
    
    # 🔥 改进错误处理，过滤AV1警告
    process = subprocess.Popen(ffmpeg_cmd, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE, 
                              text=True)

    try:
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            print(f"\n✅ 完成！处理时间: {time.time() - start_time:.2f} 秒")
            print(f"📁 输出文件: {output_video}")
            
            # 🔥 验证输出文件
            if os.path.exists(output_video):
                file_size = os.path.getsize(output_video) / (1024 * 1024)  # MB
                print(f"📊 文件大小: {file_size:.2f} MB")
                
                # 简单验证文件是否可读
                try:
                    test_video = cv2.VideoCapture(output_video)
                    frame_count = int(test_video.get(cv2.CAP_PROP_FRAME_COUNT))
                    test_video.release()
                    print(f"✅ 文件验证通过，总帧数: {frame_count}")
                except:
                    print("⚠️ 文件可能有问题，请检查")
            
        else:
            print(f"\n❌ FFmpeg执行错误:")
            # 🔥 过滤掉AV1相关的重复警告
            filtered_errors = []
            for line in stderr.split('\n'):
                if not any(keyword in line for keyword in [
                    'Missing Sequence Header',
                    'hardware accelerated AV1',
                    'Failed to get pixel format',
                    'Your platform doesn\'t suppport'
                ]):
                    if line.strip():  # 只保留非空行
                        filtered_errors.append(line)
            
            # 只显示最后几行有用的错误信息
            if filtered_errors:
                print('\n'.join(filtered_errors[-5:]))
            else:
                print("处理完成，但有一些AV1兼容性警告（已过滤）")
                
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        if process.poll() is None:
            process.kill()

# 🔥 使用示例
if __name__ == "__main__":
    # 测试模式：只处理前30秒
    # merge_subtitles_to_video(test_mode=True, test_duration=30)
    
    # 正式模式：处理完整视频
    # merge_subtitles_to_video(test_mode=False)
    
    # 或者简写
    merge_subtitles_to_video()  # 默认正式模式