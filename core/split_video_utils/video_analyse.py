import numpy as np
import librosa
import warnings

warnings.filterwarnings('ignore')

def create_terminal_30s_timeline(audio_path):
    """在终端内显示30秒音频时间线"""
    
    print("🎵 Loading 30 seconds of audio...")
    
    # 加载音频
    y, sr = librosa.load(audio_path, sr=22050, duration=30.0)
    hop_length = int(0.01 * sr)
    frame_length = hop_length * 4
    
    rms_energy = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    rms_db = librosa.amplitude_to_db(rms_energy, ref=np.max)
    time_frames = librosa.frames_to_time(np.arange(len(rms_energy)), sr=sr, hop_length=hop_length)
    
    print(f"✓ Loaded: {len(y)/sr:.2f}s, Generated {len(rms_db)} data points")
    
    # 创建终端ASCII图表
    print("\n" + "="*100)
    print("                           30-SECOND AUDIO dB TIMELINE")
    print("="*100)
    
    # 图表参数
    width = 90  # 90个字符宽度，每个字符代表约0.33秒
    height = 25  # 25行高度
    
    min_db = np.min(rms_db)
    max_db = np.max(rms_db)
    
    # 绘制主图表
    for row in range(height):
        line = ""
        db_level = max_db - (row / height) * (max_db - min_db)
        
        # 添加dB标签
        db_label = f"{db_level:6.1f}dB |"
        
        for col in range(width):
            time_idx = int((col / width) * len(rms_db))
            if time_idx < len(rms_db):
                current_db = rms_db[time_idx]
                
                if current_db >= db_level:
                    line += "█"  # 实心块
                elif current_db >= db_level - 1:
                    line += "▓"  # 深灰
                elif current_db >= db_level - 2:
                    line += "▒"  # 中灰
                elif current_db >= db_level - 3:
                    line += "░"  # 浅灰
                else:
                    line += " "  # 空白
            else:
                line += " "
        
        # 添加阈值标记
        threshold_mark = ""
        if abs(db_level - (-20)) < 1:
            threshold_mark = " ← -20dB (Strict)"
        elif abs(db_level - (-25)) < 1:
            threshold_mark = " ← -25dB (Normal)"
        elif abs(db_level - (-30)) < 1:
            threshold_mark = " ← -30dB (Sensitive)"
        elif abs(db_level - (-35)) < 1:
            threshold_mark = " ← -35dB (Ultra)"
        
        print(db_label + line + "|" + threshold_mark)
    
    # 时间轴
    time_axis = "        |"
    for i in range(0, width, 15):  # 每15个字符一个时间标记
        time_val = (i / width) * 30
        time_axis += f"{time_val:4.0f}s" + " " * 11
    print(time_axis)
    
    # 底部标尺
    scale_line = "        |"
    for i in range(0, width, 5):
        if i % 15 == 0:
            scale_line += "|"
        else:
            scale_line += "."
    print(scale_line)
    
    print("="*100)
    
    # 静音检测可视化
    print("\n" + "="*100)
    print("                         SILENCE DETECTION TIMELINE")
    print("="*100)
    
    # 创建静音检测图
    silence_levels = [
        (-20, "🔴", "STRICT"),
        (-25, "🟠", "NORMAL"), 
        (-30, "🟢", "SENSITIVE"),
        (-35, "🟣", "ULTRA")
    ]
    
    for threshold, emoji, name in silence_levels:
        line = f"{name:>10} {threshold:3d}dB |"
        
        for col in range(width):
            time_idx = int((col / width) * len(rms_db))
            if time_idx < len(rms_db):
                if rms_db[time_idx] < threshold:
                    line += "█"  # 静音
                else:
                    line += "░"  # 活跃
            else:
                line += " "
        
        # 计算静音百分比
        silent_frames = np.sum(rms_db < threshold)
        silent_percent = (silent_frames / len(rms_db)) * 100
        
        line += f"| {silent_percent:5.1f}% silent"
        print(line)
    
    # 时间轴（重复）
    time_axis = "             |"
    for i in range(0, width, 15):
        time_val = (i / width) * 30
        time_axis += f"{time_val:4.0f}s" + " " * 11
    print(time_axis)
    
    print("="*100)
    
    return time_frames, rms_db

def show_30s_detailed_analysis(time_frames, rms_db):
    """显示详细的30秒分析"""
    
    print("\n" + "🔍 DETAILED 30-SECOND ANALYSIS")
    print("="*80)
    
    # 基本统计
    max_db = np.max(rms_db)
    min_db = np.min(rms_db)
    mean_db = np.mean(rms_db)
    std_db = np.std(rms_db)
    
    print(f"📊 BASIC STATISTICS:")
    print(f"   Max dB:      {max_db:7.2f} dB")
    print(f"   Min dB:      {min_db:7.2f} dB")
    print(f"   Mean dB:     {mean_db:7.2f} dB")
    print(f"   Std Dev:     {std_db:7.2f} dB")
    print(f"   Range:       {max_db - min_db:7.2f} dB")
    
    # 每秒分析
    print(f"\n⏱️  SECOND-BY-SECOND ANALYSIS:")
    print("-" * 60)
    print(f"{'Second':<8} {'Avg dB':<8} {'Min dB':<8} {'Max dB':<8} {'Status':<12}")
    print("-" * 60)
    
    for sec in range(30):
        start_idx = np.argmin(np.abs(time_frames - sec))
        end_idx = np.argmin(np.abs(time_frames - (sec + 1)))
        
        if end_idx > start_idx:
            sec_data = rms_db[start_idx:end_idx]
            avg_db = np.mean(sec_data)
            min_sec_db = np.min(sec_data)
            max_sec_db = np.max(sec_data)
            
            # 状态判断
            if avg_db < -35:
                status = "VERY QUIET"
            elif avg_db < -30:
                status = "QUIET"
            elif avg_db < -25:
                status = "MEDIUM"
            elif avg_db < -15:
                status = "LOUD"
            else:
                status = "VERY LOUD"
            
            print(f"{sec:2d}s      {avg_db:6.1f}   {min_sec_db:6.1f}   {max_sec_db:6.1f}   {status}")
    
    # 活跃时段检测
    print(f"\n🎵 ACTIVE PERIODS (> -30dB):")
    print("-" * 40)
    
    active_mask = rms_db > -30
    in_active = False
    active_start = 0
    active_periods = []
    
    for i, is_active in enumerate(active_mask):
        if is_active and not in_active:
            active_start = i
            in_active = True
        elif not is_active and in_active:
            active_end = i - 1
            duration = time_frames[active_end] - time_frames[active_start]
            if duration > 0.1:  # 只显示超过0.1秒的活跃段
                active_periods.append({
                    'start': time_frames[active_start],
                    'end': time_frames[active_end],
                    'duration': duration,
                    'peak_db': np.max(rms_db[active_start:active_end])
                })
            in_active = False
    
    # 处理最后一段
    if in_active:
        duration = time_frames[-1] - time_frames[active_start]
        if duration > 0.1:
            active_periods.append({
                'start': time_frames[active_start],
                'end': time_frames[-1],
                'duration': duration,
                'peak_db': np.max(rms_db[active_start:])
            })
    
    if active_periods:
        for i, period in enumerate(active_periods[:10]):  # 显示前10个
            print(f"{i+1:2d}. {period['start']:6.2f}s - {period['end']:6.2f}s "
                  f"({period['duration']:5.2f}s) Peak: {period['peak_db']:6.1f}dB")
    else:
        print("   No significant active periods found")
    
    print("="*80)

def terminal_30s_complete_analysis(audio_path):
    """完整的终端30秒分析"""
    
    print("🎵 COMPLETE 30-SECOND AUDIO ANALYSIS")
    print(f"📁 File: {audio_path}")
    print("="*100)
    
    # 1. 创建终端时间线
    time_frames, rms_db = create_terminal_30s_timeline(audio_path)
    
    # 2. 详细分析
    show_30s_detailed_analysis(time_frames, rms_db)
    
    # 3. 推荐设置
    mean_db = np.mean(rms_db)
    print(f"\n💡 RECOMMENDATIONS:")
    print("-" * 30)
    
    if mean_db < -40:
        print("   🔇 Audio is very quiet - use -35dB threshold")
        print("   📝 Consider audio enhancement")
    elif mean_db < -30:
        print("   🔉 Audio is quiet - use -30dB threshold")
    elif mean_db < -20:
        print("   🔊 Audio is normal - use -25dB threshold (recommended)")
    else:
        print("   📢 Audio is loud - use -20dB threshold")
    
    print("="*100)
    
    return time_frames, rms_db

# 使用方法
if __name__ == "__main__":
    audio_file = "/home/darkchunk/code/VideoLingo/output/test_segments/segment_start_audio_vocals.mp3"
    terminal_30s_complete_analysis(audio_file)


# 切分点 1: 2.75s   (在1.5s-4.0s静音段的中点)
# 切分点 2: 7.25s   (在6.5s-8.0s静音段的中点)  
# 切分点 3: 13.25s  (在12.5s-14.0s静音段的中点)
# 切分点 4: 18.25s  (在17.5s-19.0s静音段的中点)
# 切分点 5: 23.0s   (在22.0s-24.0s静音段的中点)