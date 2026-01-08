import os
import time
import subprocess
from pathlib import Path
import pandas as pd
from rich.console import Console
from rich.panel import Panel
import json
import re
from core.prompts_storage import get_title_introduction_prompt
from core.ask_gpt import ask_gpt
from core.config_utils import load_key
import pexpect
import sys
import datetime


console = Console()

##############参数控制##################

TID=36 # 野生技术协会
################################

EXCEL_DEFAULT_PATH = os.path.join("batch", "output", "bilibili_upload_tasks.xlsx")

def method1_upload(video_path, title, tags, introduction, schedule_time, partition, collection=None, cookies_path="cookies.json"):
    # 如果当前的 biliup 不存在 就进行安装
    from shutil import which
    if which("biliup") is None:
        os.system('pip install biliup')
    # biliup login 首先进行bilibili登陆操作
    os.system('biliup login')
    # biliup 进行视频上传操作
    if not video_path or not os.path.exists(video_path):
        raise ValueError(f"视频路径不存在: {video_path}")
    args = [video_path, "--title", "\"" + (title or Path(video_path).parent.name) + "\""]
    
    
    if introduction:
        args += ["--desc", "\""+ introduction + "\""]
    if tags:
        args += ["--tag", "\"" + tags + "\""]
    if partition and str(partition).strip().isdigit():
        args += ["--tid", "\"" +  str(int(partition)) + "\""]
    if schedule_time and str(schedule_time).strip().isdigit():
        args += ["--dtime", "\"" + str(int(schedule_time)) + "\""]
    # 合集
    if collection:
        args += ["--collection", "\"" + str(int(collection)) + "\"" ] 

    # 需要先运行这个命令，阻塞当前的进程
    cmd = ["biliup"]
    if cookies_path and os.path.exists(cookies_path):
        cmd += ["-u", cookies_path]
    cmd += ["upload"] + args
    print("cmd: " + ' '.join(cmd))
    exit_code = os.system(' '.join(cmd))

    # 在 Unix 系统中，0 表示成功
    if exit_code == 0:
        print("✅ biliup login 执行成功")
        return True
    else:
        print(f"❌ biliup login 执行失败，退出码: {exit_code}")
        return False


def method2_generate_excel(output_root="batch/output", excel_path=EXCEL_DEFAULT_PATH):
    base = Path(output_root)
    rows = []

    # 获取当前时间
    now = datetime.datetime.now()
    # 获取明天的日期，时间设为18:00:00
    tomorrow_6pm = now.replace(hour=18, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    # 转换为时间戳
    base_timestamp = int(tomorrow_6pm.timestamp())
    # Debug
    # print(base_timestamp)
    # print(tomorrow_6pm)
    # print(base)
    if base.exists():
        for child in base.iterdir():
            if child.is_dir():
                preferred = child / "output_sub.mp4"
                if preferred.exists():
                    video_path = str(preferred)
                else:
                    mp4s = list(child.glob("*.mp4"))
                    video_path = str(mp4s[0]) if mp4s else ""
                desc_path = child / "log" / "sentence_splitbynlp.txt"
                desc = ""

                try:
                    if desc_path.exists():
                        desc = desc_path.read_text(encoding="utf-8").strip()
                except Exception:
                    desc = ""
                
                prompt = get_title_introduction_prompt(desc);
                # 通过调用当前的 gpt的方法来进行 标题和简介的生成
                try:    
                    desc = ask_gpt(prompt, response_json=True, log_title='subtitle_trim')      
                except Exception as e:
                    print(f"Error: {e}")
                # DEBUG
                # print("测试 :  ")
                # print(desc)
                # DEBUG
                title = desc['title']
                introduction = desc['introduction']
                tags = desc['tags']
                rows.append({
                    "视频路径": video_path,
                    "标题": title,
                    "标签": tags,
                    "描述简介": introduction,
                    "版权声明": 1,
                    "定时发布时间戳": base_timestamp,
                    "分区": TID,
                    "加入合集": ""
                })
                base_timestamp += 86400
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
    df.to_excel(excel_path, index=False, engine="openpyxl")
    console.print(Panel(f"Excel 生成完成: {excel_path}", title="[bold green]方法2[/bold green]"))
    return excel_path

def method3_upload_from_excel(excel_path=EXCEL_DEFAULT_PATH, cookies=None):
    df = pd.read_excel(excel_path)
    status_col = "Status"
    if status_col not in df.columns:
        df[status_col] = ""
    try:
        df[status_col] = df[status_col].astype(str)
    except Exception:
        pass
    for idx, row in df.iterrows():
        if str(df.at[idx, status_col]).strip().lower() == "done":
            continue
        try:
            video_path = str(row.get("视频路径", "")).strip()
            title = str(row.get("标题", ""))
            tags = str(row.get("标签", ""))
            introduction = str(row.get("描述简介", ""))
            description = str(row.get("版权声明", ""))
            schedule_time = str(row.get("定时发布时间戳", ""))
            partition = str(row.get("分区", "")) 
            collection = str(row.get("加入合集", ""))
            # 
            cookies_use = cookies if (cookies and os.path.exists(str(cookies))) else None
            console.print(Panel(
                f"视频路径: {video_path}\n"
                f"标题: {title}\n"
                f"标签: {tags}\n"
                f"描述简介: {introduction}\n"
                f"版权声明/描述: {description}\n"
                f"定时发布时间戳: {schedule_time}\n"
                f"分区:{partition}\n"
                f"加入合集: {collection}",
                title="[bold blue]上传参数[/bold blue]"
            ))
            # 
            method1_upload(
                video_path=video_path, title=title, tags=tags, introduction=introduction, schedule_time=schedule_time, partition=partition, collection=None, cookies_path="cookies.json"
            )
           
            df.at[idx, status_col] = "Done"
            console.print(Panel(f"上传完成: {row.get('视频路径', '')}", title="[bold green]方法3[/bold green]"))
        except Exception as e:
            msg = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", str(e)).replace("\n", " ").strip()
            df.at[idx, status_col] = f"Error: {msg}"
            console.print(Panel(str(e), title="[bold red]上传失败[/bold red]"))
        finally:
            df.to_excel(excel_path, index=False, engine="openpyxl")
    return True

# 生产环境
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    p1 = sub.add_parser("upload-video")
    p1.add_argument("--video", required=True)
    p1.add_argument("--cover", default="")
    p1.add_argument("--partition_tid", default="")
    p1.add_argument("--tags", default="")
    p1.add_argument("--description", default="")
    p1.add_argument("--schedule_time", default="")
    p1.add_argument("--collection", default="")
    p1.add_argument("--cookies", default="cookies.json")
    p1.add_argument("--proxy", default=None)
    p1.add_argument("--title", default=None)
    p2 = sub.add_parser("generate-excel")
    p2.add_argument("--output-root", default="batch/output")
    p2.add_argument("--excel", default=EXCEL_DEFAULT_PATH)
    p3 = sub.add_parser("upload-excel")
    p3.add_argument("--excel", default=EXCEL_DEFAULT_PATH)
    p3.add_argument("--cookies", default="cookies.json")
    p3.add_argument("--proxy", default=None)
    args = parser.parse_args()
    if args.cmd == "upload-video":
        method1_upload(
            video_path=args.video,
            cover=args.cover,
            partition_tid=args.partition_tid,
            tags=args.tags,
            description=args.description,
            schedule_time=args.schedule_time,
            collection=args.collection,
            cookies_path=args.cookies,
            proxy=args.proxy,
            title=args.title
        )
    elif args.cmd == "generate-excel":
        method2_generate_excel(output_root=args.output_root, excel_path=args.excel)
    elif args.cmd == "upload-excel":
        method3_upload_from_excel(excel_path=args.excel, cookies=args.cookies, proxy=args.proxy)
    else:
        parser.print_help()
## 测试环境
# if __name__ == '__main__':
    # method3_upload_from_excel()
    # method2_generate_excel()
#     method1_upload(
#         video_path="batch/output/segment_02/output_sub.mp4",
#         cover="",
#         partition_tid="",
#         tags="第1章：[智能合约] 无需信任-透明协议-价值互联",
#         description="""🌐 区块链的信任危机与解决方案: 
 
#  你是否曾因不信任中介机构而感到焦虑？麦当劳彩票舞弊、银行倒闭事件、Robinhood限制交易……历史一次次证明，承诺往往不堪一击。区块链智能合约应运而生，它能否终结“不信任”的怪圈？ 
 
#  🔑 智能合约：信任的基石 
 
#  智能合约是一种部署在去中心化区块链上的协议，一旦部署，便不可篡改。它像一个自动执行的数字协议，公开透明，无需人为干预。通过密码学和代码，智能合约确保了协议的公平执行，让信任不再依赖于人品，而是依赖于数学。 
 
#  💡 智能合约如何解决现实问题？ 
 
#  *   麦当劳彩票舞弊：将彩票代码部署到区块链上，每次黑客尝试篡改，所有人都会收到通知，且无法更改。 
#  *   Robinhood限制交易：使用去中心化交易所，无需中心化机构，避免单方面限制交易。 
#  *   银行倒闭：通过透明的偿付能力检查，构建类似银行的智能合约，防止资不抵债。 
 
#  🌟 智能合约的优势 
 
#  *   去中心化：无需信任中介机构，协议由去中心化网络执行。 
#  *   透明性：所有交易和代码公开可查，杜绝暗箱操作。 
#  *   高效性：交易瞬间完成，无需漫长的清算和结算。 
#  *   安全性：难以篡改，保护资产安全。 
 
#  🌱 智能合约的应用 
 
#  *   DeFi (去中心化金融)：提供无需信任的金融服务。 
#  *   DAO (去中心化自治组织)：通过智能合约实现社区自治。 
#  *   NFT (非同质化代币)：赋予数字资产独一无二的价值。 
 
#  🚀 加入智能合约的未来 
 
#  智能合约正在重塑各行各业，从金融到艺术，再到供应链管理。现在就加入这场革命，探索智能合约的无限可能！ 
 
#  #智能合约 #区块链 #去中心化 #DeFi #信任危机 #技术未来""",
#         schedule_time="",
#         collection="",
#         cookies_path="cookies.json",
#         proxy=None,
#         title=None
#     )


# 测试命令：  biliup upload  /Users/luogaiyu/code/VideoLingo/batch/output/segment_02/output_sub.mp4  --title "测试视频" --tag "测试,视频" --desc "这是一个测试视频" --copyright 1 --dtime 1767862800 --tid 36
