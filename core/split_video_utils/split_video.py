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
from rich import print as rprint

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
    rprint(f"[cyan]✂️ 提取视频片段: {format_time(start_time)} - {format_time(start_time + duration)}[/cyan]")
    
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
        rprint(f"[green]✓ 视频片段提取完成: {os.path.basename(output_path)}[/green]")
        return True
    except Exception as e:
        rprint(f"[red]❌ 视频片段提取失败: {e}[/red]")
        return False

def extract_audio_from_video(video_path, output_audio_path):
    """从视频中提取音频"""
    rprint(f"[cyan]🎵 提取音频: {os.path.basename(video_path)} -> {os.path.basename(output_audio_path)}[/cyan]")
    
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
        rprint(f"[green]✓ 音频提取完成: {os.path.basename(output_audio_path)}[/green]")
        return True
    except Exception as e:
        rprint(f"[red]❌ 音频提取失败: {e}[/red]")
        return False

def separate_vocals_with_demucs(audio_path, output_dir):
    """使用Demucs分离人声"""
    rprint(f"[cyan]🎤 使用Demucs分离人声: {os.path.basename(audio_path)}[/cyan]")
    
    try:
        # 创建临时目录
        temp_dir = os.path.join(output_dir, "demucs_temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # 运行Demucs
        cmd = [
            'python', '-m', 'demucs.separate',
            '--two-stems=vocals',
            '-o', temp_dir,
            audio_path
        ]
        
        with console.status("[yellow]🎤 分离人声中...", spinner="dots"):
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            # 查找输出文件
            audio_name = os.path.splitext(os.path.basename(audio_path))[0]
            vocals_path = None
            no_vocals_path = None
            
            # 搜索输出文件
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if 'vocals' in file and audio_name in file:
                        vocals_path = os.path.join(root, file)
                    elif 'no_vocals' in file and audio_name in file:
                        no_vocals_path = os.path.join(root, file)
            
            if vocals_path:
                # 移动到输出目录
                final_vocals_path = os.path.join(output_dir, f"{audio_name}_vocals.mp3")
                final_no_vocals_path = os.path.join(output_dir, f"{audio_name}_no_vocals.mp3")
                
                # 转换为mp3格式
                if vocals_path.endswith('.wav'):
                    subprocess.run([
                        'ffmpeg', '-i', vocals_path, 
                        '-acodec', 'libmp3lame', final_vocals_path, '-y'
                    ], capture_output=True)
                else:
                    subprocess.run(['cp', vocals_path, final_vocals_path])
                
                if no_vocals_path and no_vocals_path.endswith('.wav'):
                    subprocess.run([
                        'ffmpeg', '-i', no_vocals_path,
                        '-acodec', 'libmp3lame', final_no_vocals_path, '-y'
                    ], capture_output=True)
                elif no_vocals_path:
                    subprocess.run(['cp', no_vocals_path, final_no_vocals_path])
                
                rprint(f"[green]✓ 人声分离完成:[/green]")
                rprint(f"  [cyan]🎤 人声: {os.path.basename(final_vocals_path)}[/cyan]")
                rprint(f"  [cyan]🎵 伴奏: {os.path.basename(final_no_vocals_path)}[/cyan]")
                
                return final_vocals_path, final_no_vocals_path
            else:
                rprint(f"[red]❌ 未找到人声分离输出文件[/red]")
                return None, None
        else:
            rprint(f"[red]❌ Demucs分离失败: {result.stderr}[/red]")
            return None, None
            
    except Exception as e:
        rprint(f"[red]❌ 人声分离错误: {e}[/red]")
        return None, None

def generate_cut_segments(cut_points, total_duration):
    """根据切分点生成段落信息"""
    segments = []
    
    # 第一个段落：从开始到第一个切分点
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
        
        # 最后一个段落：从最后一个切分点到结束
        segments.append({
            'index': len(cut_points) + 1,
            'start': cut_points[-1]['actual'],
            'end': total_duration,
            'duration': total_duration - cut_points[-1]['actual'],
            'cut_type': 'end'
        })
    else:
        # 没有切分点，整个视频作为一个段落
        segments.append({
            'index': 1,
            'start': 0,
            'end': total_duration,
            'duration': total_duration,
            'cut_type': 'whole'
        })
    
    return segments

def detect_silence_fixed(audio_path, noise_db=-25, min_duration=0.1):
    """修复的静音检测函数"""
    rprint(f"[cyan]🔍 检测静音段 ({noise_db}dB, ≥{min_duration}s)...[/cyan]")
    
    cmd = [
        'ffmpeg',
        '-i', audio_path,
        '-af', f'silencedetect=noise={noise_db}dB:duration={min_duration}',
        '-f', 'null',
        '-',
        '-v', 'info'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        silence_periods = []
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
                    
                    if silence_duration >= min_duration:
                        silence_periods.append({
                            'start': current_silence_start,
                            'end': silence_end,
                            'duration': silence_duration,
                            'center': (current_silence_start + silence_end) / 2
                        })
                    
                    current_silence_start = None
                    
                except Exception:
                    continue
        
        if silence_periods:
            rprint(f"[green]✓ 找到 {len(silence_periods)} 个静音段 ({noise_db}dB, ≥{min_duration}s)[/green]")
            
            # 按时长分类
            short_silences = [s for s in silence_periods if 0.1 <= s['duration'] < 0.5]
            medium_silences = [s for s in silence_periods if 0.5 <= s['duration'] < 1.0]
            long_silences = [s for s in silence_periods if s['duration'] >= 1.0]
            
            rprint(f"  [dim]短静音(0.1-0.5s): {len(short_silences)} | "
                  f"中静音(0.5-1.0s): {len(medium_silences)} | "
                  f"长静音(1.0s+): {len(long_silences)}[/dim]")
            
            # 显示详细信息
            for i, period in enumerate(silence_periods[:10]):
                silence_type = "🔸" if period['duration'] < 0.5 else "🔹" if period['duration'] < 1.0 else "🔶"
                rprint(f"  {silence_type} {i+1:2d}. {format_time(period['start'])} - {format_time(period['end'])} "
                      f"({period['duration']:.3f}s) 中点: {format_time(period['center'])}")
            
            if len(silence_periods) > 10:
                rprint(f"  ... 还有 {len(silence_periods) - 10} 个静音段")
        else:
            rprint(f"[yellow]⚠️ 未找到符合条件的静音段 ({noise_db}dB, ≥{min_duration}s)[/yellow]")
        
        return silence_periods
        
    except Exception as e:
        rprint(f"[red]❌ 静音检测失败: {e}[/red]")
        return []

def detect_speech_pauses_fixed(audio_path, audio_type="音频"):
    """修复的人声停顿检测"""
    rprint(f"[cyan]🎤 检测{audio_type}中的人声停顿...[/cyan]")
    
    # 精细参数配置
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
            '-i', audio_path,
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
            
            if silence_periods:
                rprint(f"  [green]✓ {desc}: {len(silence_periods):3d} 个停顿[/green] "
                      f"[dim](微:{len(micro_pauses)} 短:{len(short_pauses)} 中:{len(medium_pauses)} 长:{len(long_pauses)})[/dim]")
                
                # 显示前3个停顿
                for i, period in enumerate(silence_periods[:3]):
                    if period['duration'] < 0.1:
                        icon = "🔸"
                    elif period['duration'] < 0.2:
                        icon = "🔹"
                    elif period['duration'] < 0.5:
                        icon = "🔷"
                    else:
                        icon = "🔶"
                    
                    rprint(f"    {icon} {i+1}. {format_time(period['start'])} - {format_time(period['end'])} "
                          f"({period['duration']*1000:5.0f}ms) [{period['type']}]")
                
                if len(silence_periods) > 3:
                    rprint(f"    ... 还有 {len(silence_periods) - 3} 个停顿")
            else:
                rprint(f"  [red]✗ {desc}: 0 个停顿[/red]")
                
        except Exception as e:
            rprint(f"  [red]✗ {desc}: 检测失败 - {e}[/red]")
    
    return all_results

def find_optimal_speech_cuts_fixed(all_results, target_interval_minutes=30, total_duration=None):
    """从人声停顿中找到最佳切分点"""
    rprint(f"\n[cyan]🎯 从人声停顿中寻找{target_interval_minutes}分钟间隔的最佳切分点...[/cyan]")
    
    if not total_duration:
        rprint("[red]❌ 需要提供总时长[/red]")
        return []
    
    # 选择最佳的检测结果
    best_result = None
    
    for result in all_results:
        count = result['count']
        config = result['config']
        
        if count >= 3:  # 至少要有3个停顿
            score = 0
            
            # 基础分数
            if 5 <= count <= 30:
                score += 10
            elif count >= 3:
                score += 5
            
            # 停顿类型加分
            score += result['short'] * 2
            score += result['medium'] * 1.5
            score += result['micro'] * 1
            
            # 噪音阈值加分
            if config[0] >= -20:
                score += 3
            elif config[0] >= -25:
                score += 2
            
            # 时长加分
            if 0.05 <= config[1] <= 0.15:
                score += 3
            elif 0.05 <= config[1] <= 0.2:
                score += 2
            
            result['score'] = score
            
            if best_result is None or score > best_result['score']:
                best_result = result
    
    if not best_result:
        rprint("[red]❌ 未找到合适的停顿检测结果[/red]")
        return []
    
    config = best_result['config']
    silences = best_result['silences']
    
    rprint(f"[green]🏆 选择最佳配置: {config[2]} (评分: {best_result['score']:.1f})[/green]")
    rprint(f"[yellow]📊 停顿统计: 总计{len(silences)}个 | "
          f"微停顿{best_result['micro']}个 | 短停顿{best_result['short']}个 | "
          f"中停顿{best_result['medium']}个 | 长停顿{best_result['long']}个[/yellow]")
    
    # 计算目标切分点
    target_seconds = target_interval_minutes * 60
    target_points = []
    
    current = target_seconds
    while current < total_duration - 60:
        target_points.append(current)
        current += target_seconds
    
    if not target_points:
        rprint(f"[yellow]⚠️ 音频时长不足以按{target_interval_minutes}分钟切分[/yellow]")
        return []
    
    rprint(f"[yellow]🎯 目标切分点: {len(target_points)} 个[/yellow]")
    
    cut_points = []
    
    for i, target_point in enumerate(target_points):
        rprint(f"[yellow]🔍 切分点 {i+1} (目标: {format_time(target_point)}):[/yellow]")
        
        # 在目标点前后寻找最佳停顿
        search_ranges = [15, 30, 60, 120, 300]
        
        found_cut = False
        
        for search_range in search_ranges:
            if found_cut:
                break
                
            search_start = max(0, target_point - search_range)
            search_end = min(total_duration, target_point + search_range)
            
            # 找到范围内的停顿
            candidates = []
            for silence in silences:
                if search_start <= silence['center'] <= search_end:
                    distance = abs(silence['center'] - target_point)
                    
                    # 评分系统
                    duration_score = 1.0
                    if 0.1 <= silence['duration'] <= 0.3:
                        duration_score = 2.0
                    elif 0.05 <= silence['duration'] <= 0.5:
                        duration_score = 1.5
                    
                    distance_score = 1.0 / (distance + 1)
                    
                    type_score = 1.0
                    if silence['type'] in ['句间', '自然', '段落']:
                        type_score = 1.5
                    elif silence['type'] in ['短句', '长句间']:
                        type_score = 1.3
                    
                    total_score = duration_score * distance_score * type_score
                    
                    candidates.append({
                        'silence': silence,
                        'distance': distance,
                        'score': total_score
                    })
            
            if candidates:
                candidates.sort(key=lambda x: (-x['score'], x['distance']))
                best = candidates[0]
                
                cut_points.append({
                    'target': target_point,
                    'actual': best['silence']['center'],
                    'deviation': best['silence']['center'] - target_point,
                    'silence_start': best['silence']['start'],
                    'silence_end': best['silence']['end'],
                    'silence_duration': best['silence']['duration'],
                    'silence_type': best['silence']['type'],
                    'search_range': search_range,
                    'score': best['score']
                })
                
                rprint(f"  [green]✓ 找到停顿: {format_time(best['silence']['center'])} "
                      f"(偏差 {best['silence']['center'] - target_point:+.1f}s, "
                      f"停顿 {best['silence']['duration']*1000:.0f}ms, "
                      f"类型: {best['silence']['type']}, "
                      f"搜索范围 ±{search_range}s)[/green]")
                
                found_cut = True
            else:
                rprint(f"  [yellow]⚠️ ±{search_range}s范围内无合适停顿[/yellow]")
        
        if not found_cut:
            fallback_time = min(target_point + 30, total_duration - 30)
            cut_points.append({
                'target': target_point,
                'actual': fallback_time,
                'deviation': fallback_time - target_point,
                'silence_start': fallback_time,
                'silence_end': fallback_time,
                'silence_duration': 0,
                'silence_type': 'fallback',
                'search_range': 0,
                'score': 0
            })
            rprint(f"  [red]✗ 无合适停顿，使用备选点 {format_time(fallback_time)}[/red]")
    
    return cut_points

def extract_audio_from_video_large(video_path, output_audio_path, timeout_minutes=10):
    """从大视频中提取音频，增加超时时间"""
    rprint(f"[cyan]🎵 提取音频 (大文件模式): {os.path.basename(video_path)} -> {os.path.basename(output_audio_path)}[/cyan]")
    
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vn',
        '-acodec', 'libmp3lame',
        '-ab', '128k',
        '-ar', '22050',
        '-ac', '1',
        output_audio_path,
        '-y'
    ]
    
    try:
        timeout_seconds = timeout_minutes * 60
        with console.status(f"[yellow]🎵 提取音频中... (最多等待{timeout_minutes}分钟)", spinner="dots"):
            subprocess.run(cmd, check=True, capture_output=True, timeout=timeout_seconds)
        rprint(f"[green]✓ 音频提取完成: {os.path.basename(output_audio_path)}[/green]")
        return True
    except subprocess.TimeoutExpired:
        rprint(f"[red]❌ 音频提取超时（{timeout_minutes}分钟）[/red]")
        return False
    except Exception as e:
        rprint(f"[red]❌ 音频提取失败: {e}[/red]")
        return False

def find_cut_points_from_silences(silences, target_interval_minutes=30, total_duration=None):
    """从静音段中找到最佳切分点"""
    rprint(f"[cyan]🎯 从静音段中寻找{target_interval_minutes}分钟间隔的切分点...[/cyan]")
    
    if not total_duration:
        rprint("[red]❌ 需要提供总时长[/red]")
        return []
    
    # 计算目标切分点
    target_seconds = target_interval_minutes * 60
    target_points = []
    
    current = target_seconds
    while current < total_duration - 60:
        target_points.append(current)
        current += target_seconds
    
    if not target_points:
        rprint(f"[yellow]⚠️ 音频时长不足以按{target_interval_minutes}分钟切分[/yellow]")
        return []
    
    rprint(f"[yellow]🎯 目标切分点: {len(target_points)} 个[/yellow]")
    rprint(f"[yellow]📊 可用静音段: {len(silences)} 个[/yellow]")
    
    cut_points = []
    
    for i, target_point in enumerate(target_points):
        rprint(f"[yellow]🔍 切分点 {i+1} (目标: {format_time(target_point)}):[/yellow]")
        
        # 在目标点前后寻找最佳静音段
        search_ranges = [30, 60, 120, 300, 600]
        
        found_cut = False
        
        for search_range in search_ranges:
            if found_cut:
                break
                
            search_start = max(0, target_point - search_range)
            search_end = min(total_duration, target_point + search_range)
            
            # 找到范围内的静音段
            candidates = []
            for silence in silences:
                if search_start <= silence['center'] <= search_end:
                    distance = abs(silence['center'] - target_point)
                    # 评分：静音时长越长越好，距离目标点越近越好
                    score = silence['duration'] / (distance + 1)
                    candidates.append({
                        'silence': silence,
                        'distance': distance,
                        'score': score
                    })
            
            if candidates:
                # 按评分排序
                candidates.sort(key=lambda x: (-x['score'], x['distance']))
                best = candidates[0]
                
                cut_points.append({
                    'target': target_point,
                    'actual': best['silence']['center'],
                    'deviation': best['silence']['center'] - target_point,
                    'silence_start': best['silence']['start'],
                    'silence_end': best['silence']['end'],
                    'silence_duration': best['silence']['duration'],
                    'search_range': search_range
                })
                
                rprint(f"  [green]✓ 切分点: {format_time(best['silence']['center'])} "
                      f"(偏差 {best['silence']['center'] - target_point:+.1f}s, "
                      f"静音 {best['silence']['duration']:.3f}s, "
                      f"搜索范围 ±{search_range}s)[/green]")
                
                found_cut = True
            else:
                rprint(f"  [yellow]⚠️ ±{search_range}s范围内无静音段[/yellow]")
        
        if not found_cut:
            fallback_time = min(target_point + 60, total_duration - 60)
            cut_points.append({
                'target': target_point,
                'actual': fallback_time,
                'deviation': fallback_time - target_point,
                'silence_start': fallback_time,
                'silence_end': fallback_time,
                'silence_duration': 0,
                'search_range': 0,
                'type': 'fallback'
            })
            rprint(f"  [red]✗ 无合适静音段，使用备选点 {format_time(fallback_time)}[/red]")
    
    return cut_points

def process_video_segments_25db(input_path, output_dir, segment_duration=30, target_interval=30):
    """处理视频片段并基于人声停顿检测切分点"""
    
    rprint(Panel.fit("[bold magenta]🚀 基于人声停顿的智能切分工具 (修复版)[/bold magenta]", border_style="magenta"))
    
    # 检查文件
    if not os.path.exists(input_path):
        rprint(f"[bold red]❌ 文件不存在: {input_path}[/bold red]")
        return
    
    rprint(f"[green]✓ 输入文件[/green]: [cyan]{os.path.basename(input_path)}[/cyan]")
    
    # 获取视频信息
    total_duration = get_video_duration(input_path)
    if total_duration is None:
        return
    
    rprint(f"[green]✓ 视频总时长[/green]: [yellow]{format_time(total_duration)}[/yellow]")
    
    # 检查Demucs
    if not check_demucs_installation():
        rprint("[red]❌ Demucs未安装，请运行: pip install demucs[/red]")
        return
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 提取测试片段进行分析
    test_segments = []
    
    # 开头片段
    if total_duration > segment_duration:
        test_segments.append({
            'name': 'start',
            'start': 0,
            'duration': segment_duration,
            'desc': f'开头{segment_duration}秒'
        })
    
    # 中间片段
    if total_duration > segment_duration * 4:
        middle_start = (total_duration - segment_duration) / 2
        test_segments.append({
            'name': 'middle',
            'start': middle_start,
            'duration': segment_duration,
            'desc': f'中间{segment_duration}秒'
        })
    
    if not test_segments:
        rprint(f"[red]❌ 视频太短，无法提取测试片段[/red]")
        return
    
    rprint(f"[cyan]📋 将分析 {len(test_segments)} 个测试片段[/cyan]")
    
    best_vocals_path = None
    
    # 处理测试片段
    for segment in test_segments:
        rprint(f"\n[yellow]🎬 处理{segment['desc']}片段...[/yellow]")
        
        # 提取视频片段
        video_segment_path = os.path.join(output_dir, f"segment_{segment['name']}.mp4")
        if not extract_video_segment(input_path, segment['start'], segment['duration'], video_segment_path):
            continue
        
        # 提取音频
        audio_path = os.path.join(output_dir, f"segment_{segment['name']}_audio.mp3")
        if not extract_audio_from_video(video_segment_path, audio_path):
            continue
        
        # 分析原始音频的静音段
        rprint(f"[cyan]📊 分析{segment['desc']}原始音频的静音段:[/cyan]")
        original_silences = detect_silence_fixed(audio_path, noise_db=-25, min_duration=0.1)
        
        # 分离人声
        vocals_path, no_vocals_path = separate_vocals_with_demucs(audio_path, output_dir)
        
        if vocals_path:
            best_vocals_path = vocals_path
            
            # 分析人声的静音段
            rprint(f"[cyan]📊 分析{segment['desc']}纯人声的静音段:[/cyan]")
            vocal_silences = detect_silence_fixed(vocals_path, noise_db=-25, min_duration=0.1)
            
            # 分析人声的精细停顿
            rprint(f"[cyan]🎤 分析{segment['desc']}纯人声的精细停顿:[/cyan]")
            speech_pauses = detect_speech_pauses_fixed(vocals_path, f"{segment['desc']}纯人声")
            
            # 对比分析
            rprint(f"[yellow]📈 对比分析:[/yellow]")
            rprint(f"  原始音频静音段: {len(original_silences)} 个")
            rprint(f"  纯人声静音段: {len(vocal_silences)} 个")
            
            # 统计精细停顿
            total_speech_pauses = sum(result['count'] for result in speech_pauses)
            rprint(f"  纯人声精细停顿: {total_speech_pauses} 个")
            
            if len(vocal_silences) > len(original_silences):
                rprint(f"  [green]✓ 人声分离后检测到更多静音段 (+{len(vocal_silences) - len(original_silences)})[/green]")
            elif len(vocal_silences) == len(original_silences):
                rprint(f"  [yellow]= 静音段数量相同[/yellow]")
            else:
                rprint(f"  [red]- 人声分离后静音段减少 ({len(vocal_silences) - len(original_silences)})[/red]")
            
            if total_speech_pauses > 0:
                rprint(f"  [green]✓ 成功检测到人声精细停顿！[/green]")
            else:
                rprint(f"  [yellow]⚠️ 未检测到精细停顿[/yellow]")
        
        rprint(f"[green]✅ {segment['desc']}片段分析完成[/green]")
    
    # 如果有人声文件，进行完整视频的切分点分析
    if best_vocals_path:
        rprint(f"\n[cyan]🎯 基于人声进行完整视频的{target_interval}分钟间隔切分分析...[/cyan]")
        
        # 提取完整音频进行分析
        full_audio_path = os.path.join(output_dir, "full_audio.mp3")
        if extract_audio_from_video_large(input_path, full_audio_path, timeout_minutes=15):
            # 分离完整音频的人声
            full_vocals_path, _ = separate_vocals_with_demucs(full_audio_path, output_dir)
            
            if full_vocals_path:
                # 尝试精细停顿切分
                rprint(f"[cyan]🎤 尝试基于人声精细停顿进行切分...[/cyan]")
                speech_results = detect_speech_pauses_fixed(full_vocals_path, "完整人声")
                speech_cut_points = find_optimal_speech_cuts_fixed(speech_results, target_interval, total_duration)
                
                # 备选的静音段切分
                rprint(f"[cyan]🔍 尝试基于静音段进行切分...[/cyan]")
                silence_cut_points = []
                full_silences = detect_silence_fixed(full_vocals_path, noise_db=-25, min_duration=0.3)
                
                if full_silences:
                    # 使用静音段进行切分
                    silence_cut_points = find_cut_points_from_silences(full_silences, target_interval, total_duration)
                
                # 选择最佳切分方案
                final_cut_points = []
                cut_method = ""
                
                if speech_cut_points and len(speech_cut_points) > 0:
                    final_cut_points = speech_cut_points
                    cut_method = "人声精细停顿"
                    rprint(f"[green]🏆 选择人声精细停顿切分方案[/green]")
                elif silence_cut_points and len(silence_cut_points) > 0:
                    final_cut_points = silence_cut_points
                    cut_method = "静音段"
                    rprint(f"[yellow]⚠️ 使用静音段切分方案[/yellow]")
                else:
                    rprint(f"[red]❌ 两种切分方案都未找到合适的切分点[/red]")
                
                if final_cut_points:
                    # 生成段落信息
                    segments = generate_cut_segments(final_cut_points, total_duration)
                    
                    rprint(f"\n[green]🎉 使用{cut_method}找到 {len(final_cut_points)} 个切分点，生成 {len(segments)} 个段落:[/green]")
                    
                    total_segments_duration = 0
                    for segment in segments:
                        cut_type_desc = "精细停顿" if 'silence_type' in final_cut_points[0] and final_cut_points[0]['silence_type'] != 'fallback' else "静音切分" if segment['cut_type'] == 'silence_cut' else "备选切分" if segment['cut_type'] == 'fallback' else "最终段"
                        rprint(f"  📹 段落 {segment['index']:2d}: {format_time(segment['start'])} - {format_time(segment['end'])} "
                              f"({format_time(segment['duration'])}) [{cut_type_desc}]")
                        total_segments_duration += segment['duration']
                    
                    rprint(f"\n[cyan]📊 切分统计:[/cyan]")
                    rprint(f"  总时长: {format_time(total_duration)}")
                    rprint(f"  段落总时长: {format_time(total_segments_duration)}")
                    rprint(f"  平均段落时长: {format_time(total_segments_duration / len(segments))}")
                    rprint(f"  切分方法: {cut_method}")
                    
                    # 保存切分点信息
                    cut_points_file = os.path.join(output_dir, "cut_points_speech_fixed.txt")
                    with open(cut_points_file, 'w', encoding='utf-8') as f:
                        f.write(f"基于{cut_method}的切分点信息\n")
                        f.write("=" * 50 + "\n\n")
                        
                        f.write("切分点详情:\n")
                        for i, cp in enumerate(final_cut_points):
                            f.write(f"切分点 {i+1}: {format_time(cp['actual'])}\n")
                            f.write(f"  目标时间: {format_time(cp['target'])}\n")
                            f.write(f"  偏差: {cp['deviation']:+.1f}s\n")
                            f.write(f"  静音段: {format_time(cp['silence_start'])} - {format_time(cp['silence_end'])}\n")
                            f.write(f"  静音时长: {cp['silence_duration']:.3f}s\n")
                            if 'silence_type' in cp:
                                f.write(f"  停顿类型: {cp['silence_type']}\n")
                            f.write(f"  搜索范围: ±{cp['search_range']}s\n\n")
                        
                        f.write("生成的段落:\n")
                        for segment in segments:
                            f.write(f"段落 {segment['index']}: {format_time(segment['start'])} - {format_time(segment['end'])} ({format_time(segment['duration'])})\n")
                    
                    rprint(f"[green]✓ 切分点信息已保存到: {cut_points_file}[/green]")
                else:
                    rprint("[red]❌ 未找到合适的切分点[/red]")
    
    # 显示结果总结
    rprint(Panel(
        f"[bold green]🎉 基于人声停顿的智能切分分析完成！[/bold green]\n\n"
        f"• 分析片段: [blue]{len(test_segments)}[/blue] 个\n"
        f"• 目标间隔: [yellow]{target_interval}[/yellow] 分钟\n"
        f"• 输出目录: [cyan]{output_dir}[/cyan]\n\n"
        f"[dim]💡 优先使用人声精细停顿(50ms起)，备选静音段切分\n"
        f"🔸 微停顿(50-100ms) 🔹 短停顿(100-200ms) 🔷 中停顿(200-500ms) 🔶 长停顿(500ms+)\n"
        f"📋 切分点信息已保存到 cut_points_speech_fixed.txt[/dim]",
        title="✨ 完成",
        border_style="green"
    ))

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="基于人声停顿的智能切分工具 (修复版)")
    parser.add_argument("--input", "-i", required=True, help="输入视频文件")
    parser.add_argument("--output", "-o", required=True, help="输出目录")
    parser.add_argument("--duration", "-d", type=int, default=30, help="测试片段长度（秒）")
    parser.add_argument("--interval", "-t", type=int, default=30, help="目标切分间隔（分钟）")
    
    args = parser.parse_args()
    
    process_video_segments_25db(
        input_path=args.input,
        output_dir=args.output,
        segment_duration=args.duration,
        target_interval=args.interval
    )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        main()
    else:
        # 直接调用示例
        input_video = "/home/darkchunk/code/VideoLingo/output/Learn Solidity Smart Contract Development ｜ Full 2024 Cyfrin Updraft Course.webm"
        output_directory = "/home/darkchunk/code/VideoLingo/output/test_speech_cuts_fixed"
        
        process_video_segments_25db(
            input_video, 
            output_directory, 
            segment_duration=30,
            target_interval=30  # 30分钟间隔
        )