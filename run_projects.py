#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
这个脚本用于同时启动flask-server和yolo项目

使用方法:
    python run_projects.py [项目名]
    
    - 不带参数: 同时启动两个项目
    - 带参数: 仅启动指定的项目 (flask-server 或 yolo)
"""

import os
import sys
import subprocess
import time
import argparse
from pathlib import Path
import shutil
import tempfile

# 定义项目路径
FLASK_SERVER_PATH = Path("flask-server")
YOLO_PATH = Path("yolo")

def check_venv(project_path):
    """检查虚拟环境是否存在和完整"""
    venv_path = project_path / "venv"
    
    if os.name == "nt":  # Windows
        python_exec = venv_path / "Scripts" / "python.exe"
        pip_path = venv_path / "Scripts" / "pip.exe"
    else:  # Unix/Linux/MacOS
        python_exec = venv_path / "bin" / "python"
        pip_path = venv_path / "bin" / "pip"
    
    python_exists = os.path.exists(python_exec)
    pip_exists = os.path.exists(pip_path)
    
    # 如果python存在但pip不存在，说明虚拟环境不完整
    if python_exists and not pip_exists:
        return False, python_exec, None
    
    return python_exists, python_exec, pip_path

def create_venv(project_path):
    """创建新的虚拟环境"""
    print(f"创建新的虚拟环境...")
    
    # 如果存在不完整的虚拟环境，先删除
    venv_path = project_path / "venv"
    if os.path.exists(venv_path):
        print(f"删除不完整的虚拟环境...")
        try:
            shutil.rmtree(venv_path)
        except Exception as e:
            print(f"删除虚拟环境失败: {e}")
            return False
    
    # 创建新的虚拟环境
    try:
        if os.name == "nt":  # Windows
            result = subprocess.run(
                ["python", "-m", "venv", "venv"], 
                cwd=project_path,
                capture_output=True,
                text=True
            )
        else:
            result = subprocess.run(
                ["python3", "-m", "venv", "venv"],
                cwd=project_path,
                capture_output=True,
                text=True
            )
        
        if result.returncode != 0:
            print(f"创建虚拟环境失败: {result.stderr}")
            return False
        
        print("虚拟环境创建成功")
        return True
    except Exception as e:
        print(f"创建虚拟环境时发生错误: {e}")
        return False

def copy_requirements_with_encoding(src_path, target_dir):
    """复制requirements.txt文件并确保UTF-8编码"""
    # 创建临时文件
    temp_file = os.path.join(target_dir, "requirements_utf8.txt")
    
    try:
        # 尝试不同的编码来读取文件
        encodings = ['utf-8', 'gbk', 'latin-1']
        content = None
        
        for encoding in encodings:
            try:
                with open(src_path, 'r', encoding=encoding) as f:
                    content = f.read()
                print(f"使用 {encoding} 编码成功读取 {src_path}")
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            print(f"无法以任何编码读取 {src_path}")
            return None
        
        # 以UTF-8编码写入临时文件
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return temp_file
    except Exception as e:
        print(f"处理requirements文件时出错: {e}")
        return None

def install_dependencies(python_exec, requirements_file, project_dir):
    """安装依赖"""
    print(f"检查项目依赖...")
    
    # 确保requirements.txt存在
    if not os.path.exists(requirements_file):
        print(f"错误: 找不到依赖文件 {requirements_file}")
        return False
    
    # 复制requirements.txt并处理编码问题
    temp_req_file = copy_requirements_with_encoding(requirements_file, project_dir)
    if not temp_req_file:
        print("处理依赖文件失败")
        return False
    
    # 使用python -m pip而不是直接调用pip
    print(f"安装依赖中，请稍候...")
    try:
        # 先更新pip
        upgrade_cmd = [python_exec, "-m", "pip", "install", "--upgrade", "pip"]
        subprocess.run(upgrade_cmd, cwd=project_dir, capture_output=True, text=True)
        
        # 安装依赖
        install_cmd = [python_exec, "-m", "pip", "install", "-r", temp_req_file]
        result = subprocess.run(install_cmd, cwd=project_dir, capture_output=True, text=True)
        
        # 删除临时文件
        try:
            os.remove(temp_req_file)
        except:
            pass
        
        if result.returncode != 0:
            print(f"安装依赖失败: {result.stderr}")
            return False
        
        print(f"依赖安装完成")
        return True
    except Exception as e:
        print(f"安装依赖时发生异常: {e}")
        return False

def run_flask_server(install_deps=True):
    """运行flask-server项目"""
    print("="*50)
    print("启动 flask-server 项目...")
    
    # 切换到flask-server目录
    os.chdir(FLASK_SERVER_PATH)
    
    # 检查虚拟环境
    venv_exists, python_exec, pip_exec = check_venv(Path("."))
    
    # 如果虚拟环境不完整或不存在，尝试创建
    if not venv_exists or pip_exec is None:
        venv_created = create_venv(Path("."))
        if venv_created:
            venv_exists, python_exec, pip_exec = check_venv(Path("."))
        else:
            print("无法创建完整的虚拟环境，将使用系统Python")
    
    if venv_exists and python_exec:
        print(f"使用虚拟环境: {python_exec}")
        
        # 检查并安装依赖
        if install_deps:
            if not install_dependencies(python_exec, "requirements.txt", "."):
                print("依赖安装失败，无法启动flask-server项目")
                os.chdir("..")
                return False
        
        # 启动项目
        if os.name == "nt":  # Windows
            cmd = f'"{python_exec}" app.py'
            subprocess.Popen(cmd, shell=True)
        else:
            cmd = [str(python_exec), "app.py"]
            subprocess.Popen(cmd)
    else:
        print("无法创建虚拟环境，使用系统Python")
        if os.name == "nt":
            subprocess.Popen("python app.py", shell=True)
        else:
            subprocess.Popen(["python3", "app.py"])
    
    # 返回上级目录
    os.chdir("..")
    print(f"flask-server 已在后台启动")
    return True

def run_yolo(install_deps=True):
    """运行yolo项目"""
    print("="*50)
    print("启动 yolo 项目...")
    
    # 切换到yolo目录
    os.chdir(YOLO_PATH)
    
    # 检查虚拟环境
    venv_exists, python_exec, pip_exec = check_venv(Path("."))
    
    # 如果虚拟环境不完整或不存在，尝试创建
    if not venv_exists or pip_exec is None:
        venv_created = create_venv(Path("."))
        if venv_created:
            venv_exists, python_exec, pip_exec = check_venv(Path("."))
        else:
            print("无法创建完整的虚拟环境，将使用系统Python")
    
    if venv_exists and python_exec:
        print(f"使用虚拟环境: {python_exec}")
        
        # 检查并安装依赖
        if install_deps:
            if not install_dependencies(python_exec, "requirements.txt", "."):
                print("依赖安装失败，无法启动yolo项目")
                os.chdir("..")
                return False
        
        # 启动项目
        if os.name == "nt":  # Windows
            cmd = f'"{python_exec}" app.py'
            subprocess.Popen(cmd, shell=True)
        else:
            cmd = [str(python_exec), "app.py"]
            subprocess.Popen(cmd)
    else:
        print("无法创建虚拟环境，使用系统Python")
        if os.name == "nt":
            subprocess.Popen("python app.py", shell=True)
        else:
            subprocess.Popen(["python3", "app.py"])
    
    # 返回上级目录
    os.chdir("..")
    print(f"yolo 已在后台启动")
    return True

def run_flask_server_simple():
    """不使用虚拟环境直接运行flask-server"""
    print("="*50)
    print("直接使用系统Python启动 flask-server 项目...")
    
    # 切换到flask-server目录
    os.chdir(FLASK_SERVER_PATH)
    
    # 使用系统Python启动
    if os.name == "nt":
        subprocess.Popen("python app.py", shell=True)
    else:
        subprocess.Popen(["python3", "app.py"])
    
    # 返回上级目录
    os.chdir("..")
    print(f"flask-server 已在后台启动")
    return True

def run_yolo_simple():
    """不使用虚拟环境直接运行yolo"""
    print("="*50)
    print("直接使用系统Python启动 yolo 项目...")
    
    # 切换到yolo目录
    os.chdir(YOLO_PATH)
    
    # 使用系统Python启动
    if os.name == "nt":
        subprocess.Popen("python app.py", shell=True)
    else:
        subprocess.Popen(["python3", "app.py"])
    
    # 返回上级目录
    os.chdir("..")
    print(f"yolo 已在后台启动")
    return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="启动flask-server和yolo项目")
    parser.add_argument("project", nargs="?", choices=["flask-server", "yolo"], 
                        help="要启动的项目名称 (如不提供则启动两个项目)")
    parser.add_argument("--no-deps", action="store_true", 
                        help="不检查和安装依赖")
    parser.add_argument("--simple", action="store_true",
                       help="使用系统Python直接启动，不使用虚拟环境")
    
    args = parser.parse_args()
    install_deps = not args.no_deps
    use_simple_mode = args.simple
    
    if args.project == "flask-server":
        if use_simple_mode:
            run_flask_server_simple()
        else:
            run_flask_server(install_deps)
    elif args.project == "yolo":
        if use_simple_mode:
            run_yolo_simple()
        else:
            run_yolo(install_deps)
    else:
        # 同时启动两个项目
        if use_simple_mode:
            flask_success = run_flask_server_simple()
        else:
            flask_success = run_flask_server(install_deps)
        
        time.sleep(2)  # 等待2秒再启动下一个项目
        
        if use_simple_mode:
            yolo_success = run_yolo_simple()
        else:
            yolo_success = run_yolo(install_deps)
    
    print("="*50)
    print("所有项目已启动，按Ctrl+C退出")
    
    try:
        # 保持脚本运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在退出...")

if __name__ == "__main__":
    main() 