import streamlit as st
import tempfile
import os
import logging
from pathlib import Path
from PIL import Image
import io
import numpy as np
import sys
import subprocess
import json
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter
import base64
import re
import shutil
import time
from datetime import datetime
import uuid
import platform
import contextlib
import threading
import traceback
from io import StringIO, BytesIO

# Set up enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Quality presets
QUALITY_PRESETS = {
    "480p": {"resolution": "480p", "fps": "30"},
    "720p": {"resolution": "720p", "fps": "30"},
    "1080p": {"resolution": "1080p", "fps": "60"},
    "4K": {"resolution": "2160p", "fps": "60"},
    "8K": {"resolution": "4320p", "fps": "60"}
}

# Animation speeds
ANIMATION_SPEEDS = {
    "Slow": 0.5,
    "Normal": 1.0,
    "Fast": 2.0,
    "Very Fast": 3.0
}

# Export formats
EXPORT_FORMATS = {
    "MP4 Video": "mp4",
    "GIF Animation": "gif",
    "WebM Video": "webm",
    "PNG Image Sequence": "png_sequence",
    "SVG Image": "svg"
}

# FPS options
FPS_OPTIONS = [15, 24, 30, 60, 120]

# Try to import Streamlit Ace
try:
    from streamlit_ace import st_ace
    ACE_EDITOR_AVAILABLE = True
except ImportError:
    ACE_EDITOR_AVAILABLE = False
    logger.warning("streamlit-ace not available, falling back to standard text editor")

# Enhanced package management
def ensure_packages():
    """Install required packages"""
    required_packages = {
        'manim': '0.17.3',
        'Pillow': '9.0.0',
        'numpy': '1.22.0',
        'streamlit-ace': '0.1.1',
        'pygments': '2.15.1',
        'matplotlib': '3.5.0'
    }
    
    # System dependencies for manim (Ubuntu/Debian-based systems)
    system_dependencies = [
        "libcairo2-dev",
        "pkg-config",
        "python3-dev",
        "libpango1.0-dev",
        "ffmpeg",
        "texlive-latex-recommended",
        "texlive-fonts-recommended",
        "texlive-latex-extra",
        "fonts-dejavu-core",
        "libsndfile1"
    ]
    
    with st.spinner("Checking and installing system dependencies..."):
        # Check if we're on a system that uses apt
        apt_available = False
        try:
            result = subprocess.run(
                ["which", "apt-get"],
                capture_output=True,
                text=True,
                check=False
            )
            apt_available = result.returncode == 0
        except Exception:
            apt_available = False
        
        if apt_available:
            # Install system dependencies
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Update apt
            status_text.text("Updating package lists...")
            try:
                subprocess.run(["apt-get", "update"], capture_output=True)
            except Exception as e:
                logger.warning(f"Error updating apt: {str(e)}")
            
            # Install each dependency
            for i, package in enumerate(system_dependencies):
                progress = (i / len(system_dependencies))
                progress_bar.progress(progress)
                status_text.text(f"Installing system dependency: {package}...")
                
                try:
                    result = subprocess.run(
                        ["apt-get", "install", "-y", package],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode != 0:
                        logger.warning(f"Could not install system package {package}: {result.stderr}")
                except Exception as e:
                    logger.warning(f"Error installing system package {package}: {str(e)}")
            
            progress_bar.progress(1.0)
            status_text.text("System dependencies installation complete!")
            time.sleep(0.5)
            progress_bar.empty()
            status_text.empty()
    
    # Check and install Python packages
    with st.spinner("Checking required Python packages..."):
        # First, quickly check if packages are already installed
        missing_packages = {}
        for package, version in required_packages.items():
            try:
                # Try to import the package to check if it's available
                if package == 'manim':
                    import manim
                elif package == 'Pillow':
                    import PIL
                elif package == 'numpy':
                    import numpy
                elif package == 'pygments':
                    import pygments
                elif package == 'matplotlib':
                    import matplotlib
            except ImportError:
                missing_packages[package] = version
        
        # If no packages are missing, return success immediately
        if not missing_packages:
            logger.info("All required Python packages already installed.")
            return True
        
        # If there are missing packages, install them with progress reporting
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (package, version) in enumerate(missing_packages.items()):
            try:
                progress = (i / len(missing_packages))
                progress_bar.progress(progress)
                status_text.text(f"Installing {package}...")
                
                pip_install_cmd = [sys.executable, "-m", "pip", "install", f"{package}>={version}"]
                
                result = subprocess.run(
                    pip_install_cmd, 
                    capture_output=True, 
                    text=True
                )
                
                if result.returncode != 0:
                    st.error(f"Failed to install {package}: {result.stderr}")
                    logger.error(f"Package installation failed: {package}")
                    return False
                    
            except Exception as e:
                st.error(f"Error installing {package}: {str(e)}")
                logger.error(f"Package installation error: {str(e)}")
                return False
        
        progress_bar.progress(1.0)
        status_text.text("All Python packages installed successfully!")
        time.sleep(0.5)
        progress_bar.empty()
        status_text.empty()
        return True

def install_custom_packages(package_list):
    """Install custom packages specified by the user"""
    if not package_list.strip():
        return True, "No packages specified"
    
    # Split and clean package list
    packages = [pkg.strip() for pkg in package_list.split(',') if pkg.strip()]
    
    if not packages:
        return True, "No valid packages specified"
    
    status_placeholder = st.sidebar.empty()
    progress_bar = st.sidebar.progress(0)
    
    results = []
    success = True
    
    for i, package in enumerate(packages):
        try:
            progress = (i / len(packages))
            progress_bar.progress(progress)
            status_placeholder.text(f"Installing {package}...")
            
            pip_install_cmd = [sys.executable, "-m", "pip", "install", package]
            
            result = subprocess.run(
                pip_install_cmd, 
                capture_output=True, 
                text=True
            )
            
            if result.returncode != 0:
                error_msg = f"Failed to install {package}: {result.stderr}"
                results.append(error_msg)
                logger.error(error_msg)
                success = False
            else:
                results.append(f"Successfully installed {package}")
                logger.info(f"Successfully installed custom package: {package}")
                
        except Exception as e:
            error_msg = f"Error installing {package}: {str(e)}"
            results.append(error_msg)
            logger.error(error_msg)
            success = False
    
    progress_bar.progress(1.0)
    status_placeholder.text("Installation complete!")
    time.sleep(0.5)
    progress_bar.empty()
    status_placeholder.empty()
    
    return success, "\n".join(results)

def extract_scene_class_name(python_code):
    """Extract the scene class name from Python code."""
    scene_classes = re.findall(r'class\s+(\w+)\s*\([^)]*Scene[^)]*\)', python_code)
    
    if scene_classes:
        # Return the first scene class found
        return scene_classes[0]
    else:
        # If no scene class is found, use a default name
        return "MyScene"

def highlight_code(code):
    formatter = HtmlFormatter(style='monokai')
    highlighted = highlight(code, PythonLexer(), formatter)
    return highlighted, formatter.get_style_defs()

def generate_manim_preview(python_code):
    """Generate a lightweight preview of the Manim animation"""
    try:
        # Extract scene components for preview
        scene_objects = []
        if "Circle" in python_code:
            scene_objects.append("circle")
        if "Square" in python_code:
            scene_objects.append("square")
        if "MathTex" in python_code or "Tex" in python_code:
            scene_objects.append("equation")
        if "Text" in python_code:
            scene_objects.append("text")
        if "Axes" in python_code:
            scene_objects.append("graph")
        if "ThreeDScene" in python_code or "ThreeDAxes" in python_code:
            scene_objects.append("3D scene")
        if "Sphere" in python_code:
            scene_objects.append("sphere")
        if "Cube" in python_code:
            scene_objects.append("cube")
            
        # Generate a more detailed visual preview based on extracted objects
        object_icons = {
            "circle": "⭕",
            "square": "🔲",
            "equation": "📊",
            "text": "📝",
            "graph": "📈",
            "3D scene": "🧊",
            "sphere": "🌐",
            "cube": "🧊"
        }
        
        icon_html = ""
        for obj in scene_objects:
            if obj in object_icons:
                icon_html += f'<span style="font-size:2rem; margin:0.3rem;">{object_icons[obj]}</span>'
        
        preview_html = f"""
        <div style="background-color:#000000; width:100%; height:220px; border-radius:10px; display:flex; flex-direction:column; align-items:center; justify-content:center; color:white; text-align:center;">
            <h3 style="margin-bottom:10px;">Animation Preview</h3>
            <div style="margin-bottom:15px;">
                {icon_html if icon_html else '<span style="font-size:2rem;">🎬</span>'}
            </div>
            <p>Scene contains: {', '.join(scene_objects) if scene_objects else 'No detected objects'}</p>
            <div style="margin-top:10px; font-size:0.8rem; opacity:0.8;">Full rendering required for accurate preview</div>
        </div>
        """
        return preview_html
    except Exception as e:
        logger.error(f"Preview generation error: {str(e)}")
        return f"""
        <div style="background-color:#FF0000; width:100%; height:200px; border-radius:10px; display:flex; align-items:center; justify-content:center; color:white; text-align:center;">
            <div>
                <h3>Preview Error</h3>
                <p>{str(e)}</p>
            </div>
        </div>
        """

def prepare_audio_for_manim(audio_file, target_dir):
    """Process audio file and return path for use in Manim"""
    try:
        # Create audio directory if it doesn't exist
        audio_dir = os.path.join(target_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        # Generate a unique filename
        filename = f"audio_{int(time.time())}.mp3"
        output_path = os.path.join(audio_dir, filename)
        
        # Save audio file
        with open(output_path, "wb") as f:
            f.write(audio_file.getvalue())
        
        return output_path
    except Exception as e:
        logger.error(f"Audio processing error: {str(e)}")
        return None

def mp4_to_gif(mp4_path, output_path, fps=15):
    """Convert MP4 to GIF using ffmpeg as a backup when Manim fails"""
    try:
        # Use ffmpeg for conversion with optimized settings
        command = [
            "ffmpeg",
            "-i", mp4_path,
            "-vf", f"fps={fps},scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            "-loop", "0",
            output_path
        ]
        
        # Run the conversion
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg conversion error: {result.stderr}")
            return None
            
        return output_path
        
    except Exception as e:
        logger.error(f"GIF conversion error: {str(e)}")
        return None

def generate_manim_video(python_code, format_type, quality_preset, animation_speed=1.0, audio_path=None, fps=None):
    temp_dir = None
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    log_placeholder = st.empty()
    video_data = None  # Initialize video data variable
    
    try:
        if not python_code or not format_type:
            raise ValueError("Missing required parameters")
            
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix="manim_render_")
        
        # Extract the scene class name from the code
        scene_class = extract_scene_class_name(python_code)
        logger.info(f"Detected scene class: {scene_class}")
        
        # If audio is provided, we need to modify the code to include it
        if audio_path:
            # Check if the code already has a with_sound decorator
            if "with_sound" not in python_code:
                # Add the necessary import
                if "from manim.scene.scene_file_writer import SceneFileWriter" not in python_code:
                    python_code = "from manim.scene.scene_file_writer import SceneFileWriter\n" + python_code
                
                # Add sound to the scene
                scene_def_pattern = f"class {scene_class}\\(.*?\\):"
                scene_def_match = re.search(scene_def_pattern, python_code)
                
                if scene_def_match:
                    scene_def = scene_def_match.group(0)
                    scene_def_with_sound = f"@with_sound(\"{audio_path}\")\n{scene_def}"
                    python_code = python_code.replace(scene_def, scene_def_with_sound)
                else:
                    logger.warning("Could not find scene definition to add audio")
        
        # Write the code to a file
        scene_file = os.path.join(temp_dir, "scene.py")
        with open(scene_file, "w", encoding="utf-8") as f:
            f.write(python_code)
        
        # Map quality preset to Manim quality flag
        quality_map = {
            "480p": "-ql",  # Low quality
            "720p": "-qm",  # Medium quality
            "1080p": "-qh",  # High quality
            "4K": "-qk",     # 4K quality
            "8K": "-qp"      # 8K quality (production quality)
        }
        quality_flag = quality_map.get(quality_preset, "-qm")
        
        # Handle special formats
        if format_type == "png_sequence":
            # For PNG sequence, we need additional flags
            format_arg = "--format=png"
            extra_args = ["--save_pngs"]
        elif format_type == "svg":
            # For SVG, we need a different format
            format_arg = "--format=svg"
            extra_args = []
        else:
            # Standard video formats
            format_arg = f"--format={format_type}"
            extra_args = []
        
        # Add custom FPS if specified
        if fps is not None:
            extra_args.append(f"--fps={fps}")
        
        # Show status and create progress bar
        status_placeholder.info(f"Rendering {scene_class} with {quality_preset} quality...")
        progress_bar = progress_placeholder.progress(0)
        
        # Build command
        command = [
            "manim",
            scene_file,
            scene_class,
            quality_flag,
            format_arg
        ]
        command.extend(extra_args)
        
        logger.info(f"Running command: {' '.join(command)}")
        
        # Execute the command
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Track output
        full_output = []
        output_file_path = None
        mp4_output_path = None  # Track MP4 output for GIF fallback
        
        # Animation tracking variables
        total_animations = None
        current_animation = 0
        total_frames = None
        current_frame = 0
        
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            
            full_output.append(line)
            log_placeholder.code("".join(full_output[-10:]))
            
            # Try to detect total animations
            if "Rendering animation number" in line or "Processing animation" in line:
                try:
                    # Extract current animation number
                    anim_match = re.search(r"(?:Rendering animation number|Processing animation) (\d+) (?:out of|/) (\d+)", line)
                    if anim_match:
                        current_animation = int(anim_match.group(1))
                        total_animations = int(anim_match.group(2))
                        logger.info(f"Animation progress: {current_animation}/{total_animations}")
                        
                        # Calculate progress based on animations
                        animation_progress = current_animation / total_animations
                        progress_bar.progress(animation_progress)
                        status_placeholder.info(f"Rendering {scene_class}: Animation {current_animation}/{total_animations} ({int(animation_progress*100)}%)")
                except Exception as e:
                    logger.error(f"Error parsing animation progress: {str(e)}")
            
            # Try to extract total frames information as fallback
            elif "Render animations with total frames:" in line and not total_animations:
                try:
                    total_frames = int(line.split("Render animations with total frames:")[1].strip().split()[0])
                    logger.info(f"Total frames to render: {total_frames}")
                except Exception as e:
                    logger.error(f"Error parsing total frames: {str(e)}")
            
            # Update progress bar based on frame information if animation count not available
            elif "Rendering frame" in line and total_frames and not total_animations:
                try:
                    # Extract current frame number
                    frame_match = re.search(r"Rendering frame (\d+)", line)
                    if frame_match:
                        current_frame = int(frame_match.group(1))
                        # Calculate progress as current frame / total frames
                        frame_progress = min(0.99, current_frame / total_frames)
                        progress_bar.progress(frame_progress)
                        # Update status with frame information
                        status_placeholder.info(f"Rendering {scene_class}: Frame {current_frame}/{total_frames} ({int(frame_progress*100)}%)")
                except Exception as e:
                    logger.error(f"Error parsing frame progress: {str(e)}")
            elif "%" in line and not total_animations and not total_frames:
                try:
                    # Fallback to percentage if available
                    percent = float(line.split("%")[0].strip().split()[-1])
                    progress_bar.progress(min(0.99, percent / 100))
                except:
                    pass
                    
            # Try to capture the output file path from Manim's output
            if "File ready at" in line:
                try:
                    # Combine next few lines to get the full path
                    path_parts = []
                    path_parts.append(line.split("File ready at")[-1].strip())
                    
                    # Read up to 5 more lines to get the complete path
                    for _ in range(5):
                        additional_line = process.stdout.readline()
                        if additional_line:
                            full_output.append(additional_line)
                            path_parts.append(additional_line.strip())
                            if additional_line.strip().endswith(('.mp4', '.gif', '.webm', '.svg')):
                                break
                    
                    # Join all parts and clean up
                    potential_path = ''.join(path_parts).replace("'", "").strip()
                    # Look for path pattern surrounded by quotes
                    path_match = re.search(r'([\'"]?)((?:/|[a-zA-Z]:\\).*?\.(?:mp4|gif|webm|svg))(\1)', potential_path)
                    if path_match:
                        output_file_path = path_match.group(2)
                        logger.info(f"Found output path in logs: {output_file_path}")
                        
                        # Track MP4 file for potential GIF fallback
                        if output_file_path.endswith('.mp4'):
                            mp4_output_path = output_file_path
                except Exception as e:
                    logger.error(f"Error parsing output path: {str(e)}")
        
        # Wait for the process to complete
        process.wait()
        progress_bar.progress(1.0)
        
        # IMPORTANT: Wait a moment for file system to catch up
        time.sleep(3)
        
        # Special handling for GIF format - if Manim failed to generate a GIF but we have an MP4
        if format_type == "gif" and (not output_file_path or not os.path.exists(output_file_path)) and mp4_output_path and os.path.exists(mp4_output_path):
            status_placeholder.info("GIF generation via Manim failed. Trying FFmpeg conversion...")
            
            # Generate a GIF using FFmpeg
            gif_output_path = os.path.join(temp_dir, f"{scene_class}_converted.gif")
            gif_path = mp4_to_gif(mp4_output_path, gif_output_path, fps=fps if fps else 15)
            
            if gif_path and os.path.exists(gif_path):
                output_file_path = gif_path
                logger.info(f"Successfully converted MP4 to GIF using FFmpeg: {gif_path}")
        
        # For PNG sequence, we need to collect the PNGs
        if format_type == "png_sequence":
            # Find the PNG directory
            png_dirs = []
            search_dirs = [
                os.path.join(os.getcwd(), "media", "images", scene_class, "Animations"),
                os.path.join(temp_dir, "media", "images", scene_class, "Animations"),
                "/tmp/media/images", 
            ]
            
            for search_dir in search_dirs:
                if os.path.exists(search_dir):
                    for root, dirs, _ in os.walk(search_dir):
                        for d in dirs:
                            if os.path.exists(os.path.join(root, d)):
                                png_dirs.append(os.path.join(root, d))
            
            if png_dirs:
                # Get the newest directory
                newest_dir = max(png_dirs, key=os.path.getctime)
                
                # Create a zip file with all PNGs
                png_files = [f for f in os.listdir(newest_dir) if f.endswith('.png')]
                if png_files:
                    zip_path = os.path.join(temp_dir, f"{scene_class}_pngs.zip")
                    
                    with zipfile.ZipFile(zip_path, 'w') as zipf:
                        for png in png_files:
                            png_path = os.path.join(newest_dir, png)
                            zipf.write(png_path, os.path.basename(png_path))
                    
                    with open(zip_path, 'rb') as f:
                        video_data = f.read()
                    
                    logger.info(f"Created PNG sequence zip: {zip_path}")
                else:
                    logger.error("No PNG files found in directory")
            else:
                logger.error("No PNG directories found")
        elif output_file_path and os.path.exists(output_file_path):
            # For other formats, read the output file directly
            with open(output_file_path, 'rb') as f:
                video_data = f.read()
            logger.info(f"Read output file from path: {output_file_path}")
        else:
            # If we didn't find the output path, search for files
            search_paths = [
                os.path.join(os.getcwd(), "media", "videos"),
                os.path.join(os.getcwd(), "media", "videos", "scene"),
                os.path.join(os.getcwd(), "media", "videos", scene_class),
                "/tmp/media/videos",
                temp_dir,
                os.path.join(temp_dir, "media", "videos"),
            ]
            
            # Add quality-specific paths
            for quality in ["480p30", "720p30", "1080p60", "2160p60", "4320p60"]:
                search_paths.append(os.path.join(os.getcwd(), "media", "videos", "scene", quality))
                search_paths.append(os.path.join(os.getcwd(), "media", "videos", scene_class, quality))
            
            # For SVG format
            if format_type == "svg":
                search_paths.extend([
                    os.path.join(os.getcwd(), "media", "designs"),
                    os.path.join(os.getcwd(), "media", "designs", scene_class),
                ])
            
            # Find all output files in the search paths
            output_files = []
            for search_path in search_paths:
                if os.path.exists(search_path):
                    for root, _, files in os.walk(search_path):
                        for file in files:
                            if file.endswith(f".{format_type}") and "partial" not in file:
                                file_path = os.path.join(root, file)
                                if os.path.exists(file_path):
                                    output_files.append(file_path)
                                    logger.info(f"Found output file: {file_path}")
            
            if output_files:
                # Get the newest file
                latest_file = max(output_files, key=os.path.getctime)
                with open(latest_file, 'rb') as f:
                    video_data = f.read()
                logger.info(f"Read output from file search: {latest_file}")
                
                # If the format is GIF but we got an MP4, try to convert it
                if format_type == "gif" and latest_file.endswith('.mp4'):
                    gif_output_path = os.path.join(temp_dir, f"{scene_class}_converted.gif")
                    gif_path = mp4_to_gif(latest_file, gif_output_path, fps=fps if fps else 15)
                    
                    if gif_path and os.path.exists(gif_path):
                        with open(gif_path, 'rb') as f:
                            video_data = f.read()
                        logger.info(f"Successfully converted MP4 to GIF using FFmpeg: {gif_path}")
        
        # If we got output data, return it
        if video_data:
            file_size_mb = len(video_data) / (1024 * 1024)
            
            # Clear placeholders
            progress_placeholder.empty()
            status_placeholder.empty()
            log_placeholder.empty()
            
            return video_data, f"✅ Animation generated successfully! ({file_size_mb:.1f} MB)"
        else:
            output_str = ''.join(full_output)
            logger.error(f"No output files found. Full output: {output_str}")
            
            # Check if we have an MP4 but need a GIF (special handling for GIF issues)
            if format_type == "gif":
                # Try one more aggressive search for any MP4 file
                mp4_files = []
                for search_path in [os.getcwd(), temp_dir, "/tmp"]:
                    for root, _, files in os.walk(search_path):
                        for file in files:
                            if file.endswith('.mp4') and scene_class.lower() in file.lower():
                                mp4_path = os.path.join(root, file)
                                if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                                    mp4_files.append(mp4_path)
                
                if mp4_files:
                    newest_mp4 = max(mp4_files, key=os.path.getctime)
                    logger.info(f"Found MP4 for GIF conversion: {newest_mp4}")
                    
                    # Convert to GIF
                    gif_output_path = os.path.join(temp_dir, f"{scene_class}_converted.gif")
                    gif_path = mp4_to_gif(newest_mp4, gif_output_path, fps=fps if fps else 15)
                    
                    if gif_path and os.path.exists(gif_path):
                        with open(gif_path, 'rb') as f:
                            video_data = f.read()
                        
                        # Clear placeholders
                        progress_placeholder.empty()
                        status_placeholder.empty()
                        log_placeholder.empty()
                        
                        file_size_mb = len(video_data) / (1024 * 1024)
                        return video_data, f"✅ Animation converted to GIF successfully! ({file_size_mb:.1f} MB)"
            
            return None, f"❌ Error: No output files were generated.\n\nMakim output:\n{output_str[:500]}..."
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        if progress_placeholder:
            progress_placeholder.empty()
        if status_placeholder:
            status_placeholder.error(f"Rendering Error: {str(e)}")
        if log_placeholder:
            log_placeholder.empty()
        
        return None, f"❌ Error: {str(e)}"
    
    finally:
        # CRITICAL: Only cleanup after we've captured the output data
        if temp_dir and os.path.exists(temp_dir) and video_data is not None:
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp dir: {temp_dir}")
            except Exception as e:
                logger.error(f"Failed to clean temp dir: {str(e)}")

def main():
    # Initialize session state variables if they don't exist
    if 'init' not in st.session_state:
        st.session_state.init = True
        st.session_state.video_data = None
        st.session_state.status = None
        st.session_state.code = ""
        st.session_state.temp_code = ""
        st.session_state.editor_key = str(uuid.uuid4())
        st.session_state.packages_checked = False  # Track if packages were already checked
        st.session_state.audio_path = None
        st.session_state.image_paths = []
        st.session_state.custom_library_result = ""
        st.session_state.settings = {
            "quality": "720p",
            "format_type": "mp4",
            "animation_speed": "Normal",
            "fps": 30  # Default FPS
        }

    # Page configuration with improved layout
    st.set_page_config(
        page_title="Manim Animation Studio",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Custom CSS for improved UI
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4F46E5, #818CF8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
        text-align: center;
    }
    /* Improved Cards */
    .card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1.8rem;
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.08);
        margin-bottom: 1.8rem;
        border-left: 5px solid #4F46E5;
        transition: all 0.3s ease;
    }
    .card:hover {
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.12);
        transform: translateY(-2px);
    }
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: pre-wrap;
        border-radius: 4px 4px 0 0;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #f0f4fd;
        border-bottom: 2px solid #4F46E5;
    }
    /* Buttons */
    .stButton button {
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    .preview-container {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        min-height: 200px;
    }
    .small-text {
        font-size: 0.8rem;
        color: #6c757d;
    }
    .asset-card {
        background-color: #f0f2f5;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        border-left: 4px solid #4F46E5;
    }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="main-header">
        🎬 Manim Animation Studio
    </div>
    <p style="text-align: center; margin-bottom: 2rem;">Create mathematical animations with Manim</p>
    """, unsafe_allow_html=True)

    # Check for packages ONLY ONCE per session
    if not st.session_state.packages_checked:
        if ensure_packages():
            st.session_state.packages_checked = True
        else:
            st.error("Failed to install required packages. Please try again.")
            st.stop()
    
    # Create main tabs (only editor and assets)
    tab_names = ["✨ Editor", "🎨 Assets"]
    tabs = st.tabs(tab_names)
    
    # Sidebar for rendering settings and custom libraries
    with st.sidebar:
        # Rendering settings section
        st.markdown("## ⚙️ Rendering Settings")
        
        col1, col2 = st.columns(2)
        with col1:
            quality = st.selectbox(
                "🎯 Quality",
                options=list(QUALITY_PRESETS.keys()),
                index=list(QUALITY_PRESETS.keys()).index(st.session_state.settings["quality"]),
                key="quality_select"
            )
        
        with col2:
            format_type_display = st.selectbox(
                "📦 Format",
                options=list(EXPORT_FORMATS.keys()),
                index=list(EXPORT_FORMATS.values()).index(st.session_state.settings["format_type"]) 
                      if st.session_state.settings["format_type"] in EXPORT_FORMATS.values() else 0,
                key="format_select_display"
            )
            # Convert display name to actual format value
            format_type = EXPORT_FORMATS[format_type_display]
        
        # Add FPS control
        fps = st.selectbox(
            "🎞️ FPS",
            options=FPS_OPTIONS,
            index=FPS_OPTIONS.index(st.session_state.settings["fps"]) if st.session_state.settings["fps"] in FPS_OPTIONS else 2,  # Default to 30 FPS (index 2)
            key="fps_select"
        )
        
        animation_speed = st.selectbox(
            "⚡ Speed",
            options=list(ANIMATION_SPEEDS.keys()),
            index=list(ANIMATION_SPEEDS.keys()).index(st.session_state.settings["animation_speed"]),
            key="speed_select"
        )
        
        # Apply the settings without requiring a button
        st.session_state.settings = {
            "quality": quality,
            "format_type": format_type,
            "animation_speed": animation_speed,
            "fps": fps
        }
        
        # Custom libraries section
        st.markdown("## 📚 Custom Python Libraries")
        st.markdown("Enter additional Python packages needed for your animations (comma-separated):")
        
        custom_libraries = st.text_area(
            "Libraries to install",
            placeholder="e.g., scipy, networkx, matplotlib",
            key="custom_libraries"
        )
        
        if st.button("Install Libraries", key="install_libraries_btn"):
            success, result = install_custom_packages(custom_libraries)
            st.session_state.custom_library_result = result
            
            if success:
                st.success("Installation complete!")
            else:
                st.error("Installation failed for some packages.")
        
        if st.session_state.custom_library_result:
            with st.expander("Installation Results"):
                st.code(st.session_state.custom_library_result)

    # EDITOR TAB
    with tabs[0]:
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.markdown("### 📝 Animation Editor")
            
            # Toggle between upload and type
            editor_mode = st.radio(
                "Choose how to input your code:",
                ["Type Code", "Upload File"],
                key="editor_mode"
            )
            
            if editor_mode == "Upload File":
                uploaded_file = st.file_uploader("Upload Manim Python File", type=["py"], key="code_uploader")
                if uploaded_file:
                    code_content = uploaded_file.getvalue().decode("utf-8")
                    if code_content.strip():  # Only update if file has content
                        st.session_state.code = code_content
                        st.session_state.temp_code = code_content
            
            # Code editor
            if ACE_EDITOR_AVAILABLE:
                current_code = st.session_state.code if hasattr(st.session_state, 'code') and st.session_state.code else ""
                st.session_state.temp_code = st_ace(
                    value=current_code,
                    language="python",
                    theme="monokai",
                    min_lines=20,
                    key=f"ace_editor_{st.session_state.editor_key}"
                )
            else:
                current_code = st.session_state.code if hasattr(st.session_state, 'code') and st.session_state.code else ""
                st.session_state.temp_code = st.text_area(
                    "Manim Python Code",
                    value=current_code,
                    height=400,
                    key=f"code_textarea_{st.session_state.editor_key}"
                )
            
            # Update code in session state if it changed
            if st.session_state.temp_code != st.session_state.code:
                st.session_state.code = st.session_state.temp_code
            
            # Generate button (use a form to prevent page reloads)
            generate_btn = st.button("🚀 Generate Animation", use_container_width=True, key="generate_btn")
            if generate_btn:
                if not st.session_state.code:
                    st.error("Please enter some code before generating animation")
                else:
                    # Extract scene class name
                    scene_class = extract_scene_class_name(st.session_state.code)
                    
                    # If no valid scene class found, add a basic one
                    if scene_class == "MyScene" and "class MyScene" not in st.session_state.code:
                        default_scene = """
class MyScene(Scene):
    def construct(self):
        text = Text("Default Scene")
        self.play(Write(text))
        self.wait(2)
"""
                        st.session_state.code += default_scene
                        st.session_state.temp_code = st.session_state.code
                        st.warning("No scene class found. Added a default scene.")
                        
                    with st.spinner("Generating animation..."):
                        video_data, status = generate_manim_video(
                            st.session_state.code,
                            st.session_state.settings["format_type"],
                            st.session_state.settings["quality"],
                            ANIMATION_SPEEDS[st.session_state.settings["animation_speed"]],
                            st.session_state.audio_path,
                            st.session_state.settings["fps"]
                        )
                        st.session_state.video_data = video_data
                        st.session_state.status = status
        
        with col2:
            st.markdown("### 🖥️ Preview & Output")
            
            # Preview container
            if st.session_state.code:
                with st.container():
                    st.markdown("<div class='preview-container'>", unsafe_allow_html=True)
                    preview_html = generate_manim_preview(st.session_state.code)
                    st.components.v1.html(preview_html, height=250)
                    st.markdown("</div>", unsafe_allow_html=True)
            
            # Generated output display
            if st.session_state.video_data:
                # Different handling based on format type
                format_type = st.session_state.settings["format_type"]
                
                if format_type == "png_sequence":
                    st.info("PNG sequence generated successfully. Use the download button to get the ZIP file.")
                    
                    # Add download button for ZIP
                    st.download_button(
                        label="⬇️ Download PNG Sequence (ZIP)",
                        data=st.session_state.video_data,
                        file_name=f"manim_pngs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                elif format_type == "svg":
                    # Display SVG preview
                    try:
                        svg_data = st.session_state.video_data.decode('utf-8')
                        st.components.v1.html(svg_data, height=400)
                    except Exception as e:
                        st.error(f"Error displaying SVG: {str(e)}")
                    
                    # Download button for SVG
                    st.download_button(
                        label="⬇️ Download SVG",
                        data=st.session_state.video_data,
                        file_name=f"manim_animation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.svg",
                        mime="image/svg+xml",
                        use_container_width=True
                    )
                else:
                    # Standard video display for MP4, GIF, WebM
                    try:
                        st.video(st.session_state.video_data, format=format_type)
                    except Exception as e:
                        st.error(f"Error displaying video: {str(e)}")
                        # Fallback for GIF if st.video fails
                        if format_type == "gif":
                            st.markdown("GIF preview:")
                            gif_b64 = base64.b64encode(st.session_state.video_data).decode()
                            st.markdown(f'<img src="data:image/gif;base64,{gif_b64}" alt="animation" style="width:100%">', unsafe_allow_html=True)
                    
                    # Add download button
                    st.download_button(
                        label=f"⬇️ Download {format_type.upper()}",
                        data=st.session_state.video_data,
                        file_name=f"manim_animation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}",
                        mime=f"{'image' if format_type == 'gif' else 'video'}/{format_type}",
                        use_container_width=True
                    )
            
            if st.session_state.status:
                if "Error" in st.session_state.status:
                    st.error(st.session_state.status)
                    
                    # Show troubleshooting tips
                    with st.expander("🔍 Troubleshooting Tips"):
                        st.markdown("""
                        ### Common Issues:
                        1. **Syntax Errors**: Check your Python code for any syntax issues
                        2. **Missing Scene Class**: Ensure your code contains a scene class that extends Scene
                        3. **High Resolution Issues**: Try a lower quality preset for complex animations
                        4. **Memory Issues**: For 4K animations, reduce complexity or try again
                        5. **Format Issues**: Some formats require specific Manim configurations
                        6. **GIF Generation**: If GIF doesn't work, try MP4 and we'll convert it automatically
                        
                        ### Example Code:
                        ```python
                        from manim import *
                        
                        class MyScene(Scene):
                            def construct(self):
                                circle = Circle(color=RED)
                                self.play(Create(circle))
                                self.wait(1)
                        ```
                        """)
                else:
                    st.success(st.session_state.status)

    # ASSETS TAB
    with tabs[1]:
        st.markdown("### 🎨 Asset Management")
        
        asset_col1, asset_col2 = st.columns([1, 1])
        
        with asset_col1:
            # Image uploader section
            st.markdown("#### 📸 Image Assets")
            st.markdown("Upload images to use in your animations:")
            
            # Allow multiple image uploads
            uploaded_images = st.file_uploader(
                "Upload Images", 
                type=["jpg", "png", "jpeg", "svg"], 
                accept_multiple_files=True,
                key="image_uploader_tab"
            )
            
            if uploaded_images:
                # Create a unique image directory if it doesn't exist
                image_dir = os.path.join(os.getcwd(), "manim_assets", "images")
                os.makedirs(image_dir, exist_ok=True)
                
                # Process each uploaded image
                for uploaded_image in uploaded_images:
                    # Generate a unique filename and save the image
                    file_extension = uploaded_image.name.split(".")[-1]
                    unique_filename = f"image_{int(time.time())}_{uuid.uuid4().hex[:8]}.{file_extension}"
                    image_path = os.path.join(image_dir, unique_filename)
                    
                    with open(image_path, "wb") as f:
                        f.write(uploaded_image.getvalue())
                    
                    # Store the path in session state
                    if "image_paths" not in st.session_state:
                        st.session_state.image_paths = []
                    
                    # Check if this image was already added
                    image_already_added = False
                    for img in st.session_state.image_paths:
                        if img["name"] == uploaded_image.name:
                            image_already_added = True
                            break
                    
                    if not image_already_added:
                        st.session_state.image_paths.append({
                            "name": uploaded_image.name, 
                            "path": image_path
                        })
                
                # Display uploaded images in a grid
                st.markdown("##### Uploaded Images:")
                image_cols = st.columns(3)
                
                for i, img_info in enumerate(st.session_state.image_paths[-len(uploaded_images):]):
                    with image_cols[i % 3]:
                        try:
                            img = Image.open(img_info["path"])
                            st.image(img, caption=img_info["name"], width=150)
                            
                            # Show code snippet for this specific image
                            if st.button(f"Use {img_info['name']}", key=f"use_img_{i}"):
                                image_code = f"""
# Load and display image
image = ImageMobject(r"{img_info['path']}")
image.scale(2)  # Adjust size as needed
self.play(FadeIn(image))
self.wait(1)
"""
                                if not st.session_state.code:
                                    base_code = """from manim import *
class ImageScene(Scene):
    def construct(self):
"""
                                    st.session_state.code = base_code + "\n        " + image_code.replace("\n", "\n        ")
                                else:
                                    st.session_state.code += "\n" + image_code
                                
                                st.session_state.temp_code = st.session_state.code
                                st.success(f"Added {img_info['name']} to your code!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error loading image {img_info['name']}: {e}")
            
            # Display previously uploaded images
            if st.session_state.image_paths:
                with st.expander("Previously Uploaded Images"):
                    # Group images by 3 in each row
                    for i in range(0, len(st.session_state.image_paths), 3):
                        prev_cols = st.columns(3)
                        for j in range(3):
                            if i+j < len(st.session_state.image_paths):
                                img_info = st.session_state.image_paths[i+j]
                                with prev_cols[j]:
                                    try:
                                        img = Image.open(img_info["path"])
                                        st.image(img, caption=img_info["name"], width=100)
                                        st.markdown(f"<div class='small-text'>Path: {img_info['path']}</div>", unsafe_allow_html=True)
                                    except:
                                        st.markdown(f"**{img_info['name']}**")
                                        st.markdown(f"<div class='small-text'>Path: {img_info['path']}</div>", unsafe_allow_html=True)
            
        with asset_col2:
            # Audio uploader section
            st.markdown("#### 🎵 Audio Assets")
            st.markdown("Upload audio files for background or narration:")
            
            uploaded_audio = st.file_uploader("Upload Audio", type=["mp3", "wav", "ogg"], key="audio_uploader")
            
            if uploaded_audio:
                # Create a unique audio directory if it doesn't exist
                audio_dir = os.path.join(os.getcwd(), "manim_assets", "audio")
                os.makedirs(audio_dir, exist_ok=True)
                
                # Generate a unique filename and save the audio
                file_extension = uploaded_audio.name.split(".")[-1]
                unique_filename = f"audio_{int(time.time())}.{file_extension}"
                audio_path = os.path.join(audio_dir, unique_filename)
                
                with open(audio_path, "wb") as f:
                    f.write(uploaded_audio.getvalue())
                
                # Store the path in session state
                st.session_state.audio_path = audio_path
                
                # Display audio player
                st.audio(uploaded_audio)
                
                st.markdown(f"""
                <div class="asset-card">
                    <p><strong>Audio: {uploaded_audio.name}</strong></p>
                    <p class="small-text">Path: {audio_path}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Add audio to animation
                st.markdown("#### Add Audio to Your Animation")
                
                # For with_sound decorator
                audio_code1 = f"""
# Add this import at the top of your file
from manim.scene.scene_file_writer import SceneFileWriter
# Add this decorator before your scene class
@with_sound("{audio_path}")
class YourScene(Scene):
    def construct(self):
        # Your animation code here
"""
                st.code(audio_code1, language="python")
                
                if st.button("Use This Audio in Animation", key="use_audio_btn"):
                    st.success("Audio set for next render!")

    # Help section
    with st.sidebar.expander("ℹ️ Help & Info"):
        st.markdown("""
        ### About Manim Animation Studio
        
        This app allows you to create mathematical animations using Manim, 
        an animation engine for explanatory math videos.
        
        ### Example Code
        
        ```python
        from manim import *
        
        class SimpleExample(Scene):
            def construct(self):
                circle = Circle(color=BLUE)
                self.play(Create(circle))
                
                square = Square(color=RED).next_to(circle, RIGHT)
                self.play(Create(square))
                
                text = Text("Manim Animation").next_to(VGroup(circle, square), DOWN)
                self.play(Write(text))
                
                self.wait(2)
        ```
        """)

if __name__ == "__main__":
    main()
