import os
import questionary

from cli import state as shared_state
from cli.config import (
    clear_cache, load_settings, save_settings, console
)
from cli.utils import (
    check_system_dependencies, download_default_assets_if_empty,
    discover_opencode_keys, auto_download_pexels_background
)
from cli.menus import (
    print_header, generate_script, edit_script, configure_background,
    configure_background_music, generate_fully_random_short,
    configure_settings, view_history, manage_presets_menu
)
from cli.compiler import compile_video_flow

def main():
    # Clear any leftover cache from previous runs
    clear_cache()
    
    # Check system dependencies (FFmpeg/FFprobe)
    check_system_dependencies()
    
    # Load settings from disk into shared settings dictionary
    load_settings()
    
    # Ensure default assets exist and are loaded
    download_default_assets_if_empty()
    
    # Check if there are existing settings; auto-detect key if empty
    if not shared_state.settings.get("api_key"):
        opencode_key, _ = discover_opencode_keys()
        if opencode_key:
            shared_state.settings["api_key"] = opencode_key
            if not shared_state.settings.get("base_url"):
                shared_state.settings["base_url"] = "https://opencode.ai/zen/go/v1"
            save_settings(shared_state.settings)
            
    while True:
        print_header()
        
        # Display current status in main menu
        script_status = "[green]Ready[/]" if shared_state.state["script_text"] else "[red]Empty[/]"
        
        # Background video status string
        if shared_state.state["bg_video_path"]:
            top_name = "Random Selection" if shared_state.state["bg_video_path"] == "random" else os.path.basename(shared_state.state["bg_video_path"])
            if shared_state.state["bg_video_bottom_path"]:
                bot_name = "Random Selection" if shared_state.state["bg_video_bottom_path"] == "random" else os.path.basename(shared_state.state["bg_video_bottom_path"])
                bg_status = f"[green]Split Screen (Top: {top_name} | Bottom: {bot_name})[/]"
            else:
                bg_status = f"[green]Full Screen (Top: {top_name})[/]"
        else:
            bg_status = "[red]Not configured[/]"
            
        bg_music_status = f"[green]Loaded ({os.path.basename(shared_state.state['bg_music_path'])})[/]" if shared_state.state["bg_music_path"] else "[yellow]None[/]"
        
        preset_status = f"[green]{shared_state.state['loaded_preset_name']}[/]" if shared_state.state.get("loaded_preset_name") else "[yellow]None (Custom/Manual)[/]"
        active_font = shared_state.state.get("sub_font") or shared_state.settings.get("sub_font", "Arial")
        active_size = shared_state.state.get("sub_size") or shared_state.settings.get("sub_size", 72)
        active_color = shared_state.state.get("sub_color") or shared_state.settings.get("sub_color", "#FFFFFF")
        
        console.print(f"Active Preset/Template: {preset_status}")
        console.print(f"Active Subtitle Style: [cyan]{active_font} ({active_size}px, {active_color})[/]")
        console.print(f"Current Script Status: {script_status}")
        console.print(f"Background Video Loop: {bg_status}")
        console.print(f"Background Music Track: {bg_music_status}")
        console.print(f"TTS Voice: [cyan]{shared_state.state['selected_voice']}[/]")
        console.print()
        
        menu_choices = [
            questionary.Choice(title="1. Generate Viral Script", value="generate"),
            questionary.Choice(title="2. Edit Current Script", value="edit"),
            questionary.Choice(title="3. Configure Background Video", value="bg"),
            questionary.Choice(title="4. Configure Background Music", value="music"),
            questionary.Choice(title="5. Compile TikTok Short", value="compile"),
            questionary.Choice(title="6. Generate Fully Random Short", value="random_short"),
            questionary.Choice(title="7. Configure App & API Settings", value="settings"),
            questionary.Choice(title="8. View History / Manage Videos", value="history"),
            questionary.Choice(title="9. Preset Templates", value="presets"),
            questionary.Choice(title="10. Exit", value="exit"),
        ]
        
        choice = questionary.select("Select an action:", choices=menu_choices).ask()
        
        if choice == "exit" or choice is None:
            console.print("[bold green]Goodbye![/]")
            break
            
        print_header()
        
        if choice == "generate":
            generate_script()
        elif choice == "edit":
            edit_script()
        elif choice == "bg":
            bg_submenu = questionary.select(
                "Configure Background Video Layout:",
                choices=[
                    questionary.Choice("1. Configure Top Video (Primary Content)", "top"),
                    questionary.Choice("2. Configure Bottom Video (Satisfying Loop / Split Screen)", "bottom"),
                    questionary.Choice("3. Auto-download Video from Pexels (Based on Script Keywords)", "pexels"),
                    questionary.Choice("4. Disable Split Screen (Use Full Screen Top Video)", "disable_split"),
                    questionary.Choice("<- Back to Main Menu", "back")
                ]
            ).ask()
            if bg_submenu == "top":
                configure_background("top")
                shared_state.state["loaded_preset_name"] = None
            elif bg_submenu == "bottom":
                configure_background("bottom")
                shared_state.state["loaded_preset_name"] = None
            elif bg_submenu == "pexels":
                pos = questionary.select(
                    "Assign Pexels video to:",
                    choices=[
                        questionary.Choice("Top Video (Primary Content)", "top"),
                        questionary.Choice("Bottom Video (Satisfying Loop / Split Screen)", "bottom")
                    ]
                ).ask()
                if pos:
                    auto_download_pexels_background(pos)
                    shared_state.state["loaded_preset_name"] = None
            elif bg_submenu == "disable_split":
                shared_state.state["bg_video_bottom_path"] = None
                shared_state.state["loaded_preset_name"] = None
                console.print("[green]Split screen disabled. Video will render full screen using Top Video.[/]")
        elif choice == "music":
            configure_background_music()
            shared_state.state["loaded_preset_name"] = None
        elif choice == "compile":
            compile_video_flow()
        elif choice == "random_short":
            generate_fully_random_short()
        elif choice == "settings":
            configure_settings()
            shared_state.state["loaded_preset_name"] = None
        elif choice == "history":
            view_history()
        elif choice == "presets":
            manage_presets_menu()
            
        # Pause before returning to the main menu
        if choice != "history":
            questionary.press_any_key_to_continue("Press any key to return to the main menu...").ask()
