from flet import *
import os
import shutil
import platform
import subprocess
import threading
import requests
import configparser
from pathlib import Path
from typing import List, Dict
import uuid

HOMEDIR = os.path.expanduser("~")
DEFAULTDIR = os.path.abspath(os.path.join(HOMEDIR,"Music"))
YTDLP_INSTALLED = bool(False)
ytdlp_version = str("")

system = platform.system()
print(f"Detected OS: {system}")

if shutil.which("yt-dlp"):
    print("✅ yt-dlp is already installed.")
    YTDLP_INSTALLED = True
    if platform.system() != "Windows":
        process = subprocess.run(args=["yt-dlp","--version"],text=True,check=True,stdout=subprocess.PIPE)
    else:
        process = subprocess.run(args=["yt-dlp","--version"],text=True,check=True,stdout=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    ytdlp_version = process.stdout.strip()
else:
    print("❌ yt-dlp not found. Attempting to download...")
    YTDLP_INSTALLED = False

def get_profiles_browser(browser_key: str) -> List[Dict[str,str]]:
    """
    Firefox及びFirefox派生のブラウザからプロファイルを取得するやつ
    """
    if browser_key not in ("firefox","floorp","zen"):
        return []
    display_name = "Firefox" if browser_key == "firefox" else "Floorp"
    browser_names = [display_name]

    candidates = []

    if system == "Windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            if browser_key == "firefox":
                candidates.append(Path(appdata) / "Mozilla" / "Firefox")
            elif browser_key == "floorp":
                candidates.append(Path(appdata) / "Floorp")
            elif browser_key == "zen":
                candidates.append(Path(appdata) / "zen")
    elif system == "Darwin":
        home = Path.home()
        name = "Firefox" if browser_key == "firefox" else "Floorp"
        candidates.append(home / "Library" / "Application Support" / name)
    elif system == "Linux":
        home = Path.home()
        name_lower = browser_key
        candidates.append(home / ".mozilla" / name_lower / "Profiles")
        candidates.append(home / ".mozilla" / name_lower)
        if browser_key == "floorp":
            candidates.append(home / ".floorp" / "Profiles")
            candidates.append(home / ".floorp")
        elif browser_key == "zen":
            candidates.append(home / ".zen")
    else:
        return []
    
    profiles = []
    seen_paths = set()

    for base_dir in candidates:
        profiles_ini = base_dir / "profiles.ini"
        if not profiles_ini.exists():
            continue

        config = configparser.ConfigParser()
        try:
            config.read(profiles_ini, encoding="utf-8")
        except Exception:
            continue

        for section in config.sections():
            if not section.startswith("Profile"):
                continue

            try:
                name = config[section].get("Name", "Unknown")
                relative = config[section].get("IsRelative", "0") == "1"
                path = config[section].get("Path", "")

                profile_path = (base_dir / path) if relative else Path(path)

                if profile_path.exists() and str(profile_path) not in seen_paths:
                    profiles.append({
                        "name": name,
                        "path": str(profile_path.resolve()),
                    })
                    seen_paths.add(str(profile_path))
            except Exception:
                continue

    return profiles

def main(page:Page) -> None:
    page.title = "watl"
    page.theme = Theme(color_scheme_seed=Colors.GREEN)
    page.theme_mode = ThemeMode.LIGHT
    page.window.center()
    page.fonts = {
        "SpaceMono": "https://github.com/google/fonts/raw/refs/heads/main/ofl/spacemono/SpaceMono-Regular.ttf"
    }
    log_lines = []

    def update_log(entry:str):
        log_lines.append(entry)
        if len(log_lines) > 1000:
            log_lines.pop(0)
        log_text.value = "\n".join(log_lines)
        log_view.scroll_to(-1)

    def yt_dlp_check():
        if not YTDLP_INSTALLED:
            page.open(
                check_modal
            )
            page.update()
        else:
            update_log(f"ℹ️ yt-dlpのバージョン: {ytdlp_version}")
            page.update()
    
    def download_yt_dlp(e):
        """
        yt-dlpのダウンロード.
        Nightly Releaseを使用する.
        """

        if not YTDLP_INSTALLED:
            page.close(check_modal)
            if system == "Windows":
                url = "https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp.exe"
                filename = "yt-dlp.exe"
            elif system == "Linux":
                url = "https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp"
                filename = "yt-dlp"
            else:
                update_log("⚠️ このOSはサポートされていません。手動でダウンロードしてください。")
                page.update()
                return

            try:
                progress_bar.value = None
                update_log(f"📥 ダウンロード開始: {filename}。")
                page.update()

                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
                    downloaded = 0

                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    progress_bar.value = downloaded / total_size
                                else:
                                    progress_bar.value = None
                                page.update()

                    if system == "Linux":
                        os.chmod(filename, 0o755)
                        print("🔒 実行権限を付与しました。")

                    progress_bar.value = 1.0
                    update_log(f"✅ {filename} をダウンロードしました。")
                    page.update()

            except Exception as e:
                progress_bar.value = 0
                update_log(f"❌ ダウンロード失敗: {e}")
                page.update()

    # ダウンロード処理
    def download(e):
        """
        ダウンロード処理
        """
        url = url_input.value
        output_path = output_path_input.value
        selected_browser = cookies_browser_dropdown.value
        profile_path = cookies_profile_dropdown.value

        print(selected_browser)
        print(profile_path)

        if not url:
            page.open(SnackBar(Text("URLが入力されていません。"),bgcolor=Colors.RED_500))
            page.update()
            return
        if not output_path:
            output_path = DEFAULTDIR
            page.open(SnackBar(Text(f"保存先が指定されていません。\nデフォルトの保存先({DEFAULTDIR})に保存されます。"),bgcolor=Colors.RED_500))
            output_path_input.value = output_path
            page.update()
            return
        
        def run_download():
            progress_template = "[DOWNLOADING]:%(progress._percent)s\t%(info.title)s"
            
            cmd = [
                "yt-dlp",
                "--no-warnings","--newline","--no-colors",
                "--progress-template",progress_template,
                "--embed-metadata",
                "--embed-thumbnail","--convert-thumbnails","jpg"
            ]

            if selected_browser:
                if selected_browser not in ("firefox","floorp"):
                    cmd.extend(["--cookies-from-browser",selected_browser])
                elif selected_browser in ("firefox","floorp"):
                    if profile_path:
                        cmd.extend(["--cookies-from-browser",f"firefox:{profile_path}"])

            # サービスによって自動で
            if 'music.youtube.com' in url:
                cmd.extend(["-f","bestaudio/best","-x","--audio-format","mp3","--audio-quality","0","--postprocessor-args","ThumbnailsConvertor:-qmin 1 -q:v 1 -vf crop=\"'if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'\""])
                if 'list=' in url:
                    cmd.extend(["-o",f"{output_path}/%(album)s/%(playlist_index)02d - %(title)s.%(ext)s","--parse-metadata","%(playlist_index)s/%(n_entries)s:%(track_number)s","--parse-metadata", "%(upload_date).4s:%(meta_date)s","--parse-metadata", "%(creators.0)s:%(album_artist)s"])
                else:
                    cmd.extend(["-o",f"{output_path}/%(title)s.%(ext)s"])
            elif 'youtube.com' in url:
                cmd.extend(["-f","bestvideo[ext=mp4]+bestaudio[ext=m4a]/best","--merge-output-format","mp4"])
                if 'list=' in url:
                    cmd.extend(["-o",f"{output_path}/%(playlist_title)s/%(title)s.%(ext)s"])
                else:
                    cmd.extend(["-o",f"{output_path}/%(title)s.%(ext)s"])
            else:
                cmd.extend(["-f","best","--merge-output-format","mp4"])
            
            cmd.append(url)

            try:
                if platform.system() != "Windows":
                    process = subprocess.Popen(cmd,bufsize=1,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
                else:
                    process = subprocess.Popen(cmd,bufsize=1,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,creationflags=subprocess.CREATE_NO_WINDOW)
                while True:
                    output = process.stdout.readline()
                    if output == "" and process.poll() is not None:
                        break
                    if output:
                        log_entry = output.strip()
                        if log_entry.startswith("[DOWNLOADING]:"):
                            progress = output.split("[DOWNLOADING]:")[1].split("\t")[0].strip()
                            title = output.split("[DOWNLOADING]:")[1].split("\t")[1].strip()
                            progress_bar.value = float(progress) / 100
                            progress_title.value = title
                            page.update()
                        else:
                            progress_bar.value = None
                            update_log(log_entry)
                            page.update()
                
                process.wait()

                if process.returncode != 0:
                    print("エラー起きてんだよ")
                    progress_bar.value = 0
                    progress_title.value = ""
                    update_log("❌ ダウンロードに失敗しました。")
                    page.update()
                else:
                    print("エラー起きんかったわ")
                    progress_bar.value = 1
                    progress_title.value = ""
                    update_log("✅ ダウンロードが完了しました。")
                    page.update()
            
            except Exception as e:
                print(e)
            
            finally:
                print("おわり")
        
        threading.Thread(target=run_download,daemon=True).start()

    def output_path_pick(e:FilePickerResultEvent):
        before = output_path_input.value
        output_path_input.value = os.path.abspath(e.path) if e.path else before
        output_path_input.update()
    
    output_path_pick_dialog = FilePicker(on_result=output_path_pick)
    page.overlay.append(output_path_pick_dialog)
    
    def on_search_profiles(e):
        selected_browser = cookies_browser_dropdown.value

        cookies_profile_dropdown.key = str(uuid.uuid4())
        cookies_profile_dropdown.value = ""
        cookies_profile_dropdown.options.clear()
        cookies_profile_dropdown.disabled = True
        page.update()

        if not selected_browser:
            page.update()
            return

        if selected_browser not in ("firefox", "floorp","zen"):
            page.open(SnackBar(Text(f"選択したブラウザー({selected_browser})はプロファイル検索に対応していません。")))
            page.update()
            return

        profiles = get_profiles_browser(selected_browser)
        if not profiles:
            page.open(SnackBar(Text(f"プロファイルが見つかりませんでした。")))
            page.update()
            return

        page.open(SnackBar(Text(f"{len(profiles)}件のプロファイルが見つかりました。")))
        cookies_profile_dropdown.options = [
            DropdownOption(key=p["path"], text=p["name"]) for p in profiles
        ]
        cookies_profile_dropdown.disabled = False
        page.update()
        print("見つかった")
    
    # 要素の定義
    url_input = TextField(label="URL")
    output_path_input = TextField(value=DEFAULTDIR,label="保存先",expand=1)
    output_path_btn = TextButton(text="選択",icon=Icons.FOLDER,on_click=lambda _:output_path_pick_dialog.get_directory_path(
        dialog_title="保存先を選択",initial_directory=output_path_input.value
    ))

    cookies_browser_dropdown = Dropdown(label="ブラウザー",options=[DropdownOption(key="chrome",text="Chrome"),DropdownOption(key="brave",text="Brave"),DropdownOption(key="firefox",text="Firefox"),DropdownOption(key="floorp",text="Floorp"),DropdownOption(key="zen",text="Zen Browser")],expand=1,on_change=on_search_profiles)
    cookies_profile_dropdown = Dropdown(label="プロファイル",options=[],expand=1)
    load_profile_btn = TextButton(text="プロファイルを検索",icon=Icons.SEARCH,on_click=on_search_profiles)

    progress_bar = ProgressBar(value=0,border_radius=border_radius.all(10))
    progress_title = TextField(label="ダウンロード中のタイトル",read_only=True)
    log_text = Text(value="",selectable=True,font_family="SpaceMono")
    log_view = Column(scroll=ScrollMode.AUTO,spacing=4,controls=[Text("ログ",size=18,style=FontWeight.BOLD),log_text])

    download_btn = FloatingActionButton(text="ダウンロード",icon=Icons.DOWNLOAD,on_click=download)

    check_modal = AlertDialog(
        title=Text("info"),
        content=Text("yt-dlpがインストールされていません。\nダウンロードしますか？"),
        actions=[
            TextButton(text="ダウンロードする",icon=Icons.DOWNLOAD,on_click=download_yt_dlp),
            TextButton(text="閉じる",on_click=lambda e:page.close(check_modal))
        ]
    )
    
    # 要素を追加
    page.floating_action_button = download_btn
    page.add(
        url_input,
        Row([output_path_input,output_path_btn]),
        Row([cookies_browser_dropdown,cookies_profile_dropdown,load_profile_btn]),
        progress_title,
        Container(log_view,width=float("inf"),height=300,padding=10,border=border.all(1),border_radius=border_radius.all(8)),
        progress_bar
    )
    yt_dlp_check()

if __name__ == "__main__":
    app(target=main)