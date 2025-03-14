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
from transformers import pipeline
import torch
import re
import shutil

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_packages():
    required_packages = {
        'manim': '0.17.3',
        'Pillow': '9.0.0',
        'numpy': '1.22.0',
        'transformers': '4.30.0',
        'torch': '2.0.0',
        'pygments': '2.15.1'
    }
    
    for package, version in required_packages.items():
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "install", f"{package}>={version}"], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                st.error(f"Failed to install {package}: {result.stderr}")
                logger.error(f"Package installation failed: {package}")
                return False
        except Exception as e:
            st.error(f"Error installing {package}: {str(e)}")
            logger.error(f"Package installation error: {str(e)}")
            return False
    return True

@st.cache_resource
def init_ai_models():
    try:        
        code_model = pipeline(
            "text-generation",
            model="deepseek-ai/deepseek-coder-1.3b-base",
            trust_remote_code=True
        )
        if code_model is None:
            st.error("Failed to initialize code model")
            return None
        return {
            "code_model": code_model,
        }
    except Exception as e:
        st.error(f"Failed to load AI models: {str(e)}")
        logger.error(f"AI model initialization error: {str(e)}")
        return None
def suggest_code_completion(code_snippet, models):
    if not models or "code_model" not in models:
        st.error("AI models not properly initialized")
        return None
        
    try:
        prompt = f"""Write a complete Manim animation scene based on this code or idea:
{code_snippet}

The code should be a complete, working Manim animation that includes:
- Proper Scene class definition
- Constructor with animations
- Proper use of self.play() for animations
- Proper wait times between animations

Here's the complete Manim code:
```python
"""
        response = models["code_model"](
            prompt, 
            max_length=1024,
            do_sample=True,
            temperature=0.2,
            top_p=0.95,
            top_k=50,
            num_return_sequences=1,
            truncation=True,
            pad_token_id=50256
        )
        
        if not response or not response[0].get('generated_text'):
            st.error("No valid completion generated")
            return None
            
        completed_code = response[0]['generated_text']
        if "```python" in completed_code:
            completed_code = completed_code.split("```python")[1].split("```")[0]
        
        if "Scene" not in completed_code:
            completed_code = f"""from manim import *

class MotivationAndTheoremWithAudioScene(Scene):
    def construct(self):
        {completed_code}"""
        
        st.code(completed_code, language='python')
        
        if st.button("Preview Generated Code"):
            try:
                video_data, status = generate_manim_video(
                    completed_code, 
                    "mp4", 
                    "Draft",
                    "#000000"
                )
                if video_data:
                    st.video(video_data)
                else:
                    st.error(f"Failed to generate preview: {status}")
            except Exception as e:
                st.error(f"Preview generation error: {str(e)}")
                logger.error(f"Preview generation error: {str(e)}")
        
        return completed_code
    except Exception as e:
        st.error(f"Error suggesting code: {str(e)}")
        logger.error(f"Code suggestion error: {str(e)}")
        return None

# Templates dictionary
TEMPLATES = {
    "Basic Scene": '''from manim import *

class MotivationAndTheoremWithAudioScene(Scene):
    def construct(self):
        # Create the title
        title = Text("Welcome to Manim", color=BLUE)
        self.play(Write(title))
        self.wait(1)
        self.play(title.animate.to_edge(UP))
        self.wait(1)
        
        # Create and animate basic shapes
        circle = Circle(radius=2.0, color=RED)
        square = Square(side_length=4.0, color=GREEN)
        
        self.play(Create(circle))
        self.wait(1)
        
        self.play(Transform(circle, square))
        self.wait(1)
        
        # Add final text
        text = Text("Thank you!", color=YELLOW).next_to(circle, DOWN)
        self.play(Write(text))
        self.wait(2)
''',
    "Mathematical Animation": '''from manim import *

class MotivationAndTheoremWithAudioScene(Scene):
    def construct(self):
        # Create equation
        equation = MathTex(
            "\\frac{d}{dx}(x^n) = nx^{n-1}",
            color=WHITE
        )
        self.play(Write(equation))
        self.wait(1)
        
        # Add explanation
        explanation = Text(
            "Power Rule of Differentiation",
            color=YELLOW,
            font_size=24
        ).next_to(equation, DOWN)
        self.play(FadeIn(explanation))
        self.wait(1)
        
        # Transform to example
        example = MathTex(
            "\\frac{d}{dx}(x^3) = 3x^2",
            color=GREEN
        )
        self.play(Transform(equation, example))
        self.wait(2)
''',"Graph Animation": '''from manim import *

class MotivationAndTheoremWithAudioScene(Scene):
    def construct(self):
        # Create coordinate system
        ax = Axes(
            x_range=[-3, 3],
            y_range=[-2, 2],
            axis_config={"color": BLUE},
            x_length=6,
            y_length=4
        )
        
        # Create graphs
        sin_graph = ax.plot(lambda x: np.sin(x), color=RED)
        cos_graph = ax.plot(lambda x: np.cos(x), color=GREEN)
        
        # Labels
        sin_label = Text("sin(x)", color=RED, font_size=24).next_to(ax, UP)
        cos_label = Text("cos(x)", color=GREEN, font_size=24).next_to(sin_label, RIGHT)
        
        # Animations
        self.play(Create(ax))
        self.play(Create(sin_graph), Write(sin_label))
        self.wait(1)
        self.play(Create(cos_graph), Write(cos_label))
        self.wait(2)
''',
    "3D Scene": '''from manim import *

class MotivationAndTheoremWithAudioScene(ThreeDScene):
    def construct(self):
        # Set up 3D axes
        axes = ThreeDAxes()
        self.set_camera_orientation(phi=75 * DEGREES, theta=30 * DEGREES)
        
        # Create 3D objects
        sphere = Sphere(radius=1, resolution=(20, 20))
        cube = Cube(side_length=1.5)
        
        # Add colors and styling
        sphere.set_color(RED)
        cube.set_color(BLUE)
        cube.set_opacity(0.5)
        
        # Animations
        self.play(Create(axes))
        self.begin_ambient_camera_rotation(rate=0.2)
        self.play(Create(sphere))
        self.wait(1)
        self.play(Transform(sphere, cube))
        self.wait(2)
        self.stop_ambient_camera_rotation()
'''
}

# Quality presets
QUALITY_PRESETS = {
    "Draft": {"resolution": "480p", "fps": "15"},
    "Medium": {"resolution": "720p", "fps": "30"},
    "High": {"resolution": "1080p", "fps": "60"}
}

# Color palettes
COLOR_PALETTES = {
    "Classic Dark": {"background": "#000000", "primary": "#FFFFFF", "secondary": "#FF0000", "accent": "#00FF00"},
    "Light Mode": {"background": "#FFFFFF", "primary": "#000000", "secondary": "#3498DB", "accent": "#E74C3C"},
    "Ocean": {"background": "#1A1A2E", "primary": "#E0E0E0", "secondary": "#4682B4", "accent": "#40E0D0"},
    "Forest": {"background": "#0B2027", "primary": "#C2C2C2", "secondary": "#40798C", "accent": "#70A9A1"},
    "Sunset": {"background": "#1A0F2C", "primary": "#F7F7F7", "secondary": "#FF6B6B", "accent": "#4ECDC4"}
}

# Animation speeds
ANIMATION_SPEEDS = {
    "Slow": 0.5,
    "Normal": 1.0,
    "Fast": 2.0,
    "Very Fast": 3.0
}
def highlight_code(code):
    formatter = HtmlFormatter(style='monokai')
    highlighted = highlight(code, PythonLexer(), formatter)
    return highlighted, formatter.get_style_defs()

def export_scene(code, settings):
    try:
        return base64.b64encode(json.dumps({
            "code": code,
            "settings": settings
        }).encode()).decode()
    except Exception as e:
        logger.error(f"Scene export error: {str(e)}")
        return None

def import_scene(data):
    try:
        decoded = json.loads(base64.b64decode(data.encode()).decode())
        return decoded["code"], decoded["settings"]
    except Exception as e:
        logger.error(f"Scene import error: {str(e)}")
        return None, None

def generate_manim_video(python_code, format_type, quality_preset, background_color, animation_speed=1.0):
    temp_dir = None
    try:
        if not python_code or not format_type or not quality_preset:
            raise ValueError("Missing required parameters")
            
        if quality_preset not in QUALITY_PRESETS:
            raise ValueError(f"Invalid quality preset: {quality_preset}")
            
        temp_dir = tempfile.mkdtemp()
        media_dir = os.path.join(temp_dir, "media")
        os.makedirs(media_dir, exist_ok=True)
        
        # Prepare the imports and config
        imports = "from manim import *\n"
        config_code = f"""config.media_dir = "{media_dir}"
config.background_color = "{background_color}"
config.frame_rate = {int(float(QUALITY_PRESETS[quality_preset]['fps']) * animation_speed)}
"""

        # Create the scene file
        scene_file = os.path.join(temp_dir, "scene.py")
        with open(scene_file, "w") as f:
            final_code = imports + config_code + python_code
            f.write(final_code)
        
        # Get quality settings
        preset = QUALITY_PRESETS[quality_preset]
        quality = "-ql" if preset["resolution"] == "480p" else "-qh"
        
        # Run manim command
        command = [
            "manim",
            scene_file,
            "MotivationAndTheoremWithAudioScene",
            quality,
            f"--format={format_type}",
            f"--fps={preset['fps']}",
            "--media_dir", media_dir
        ]
        
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=temp_dir
        )
        
        if result.returncode != 0:
            logger.error(f"Manim error: {result.stderr}")
            return None, f"❌ Error: {result.stderr}"
        
        videos_dir = os.path.join(media_dir, "videos")
        if not os.path.exists(videos_dir):
            logger.error("Videos directory not found")
            return None, "❌ Videos directory not found"
        
        video_files = []
        for root, _, files in os.walk(videos_dir):
            for file in files:
                if file.endswith(f".{format_type}"):
                    video_files.append(os.path.join(root, file))
        
        if not video_files:
            logger.error(f"No {format_type} files generated")
            return None, f"❌ No {format_type} files generated"
        
        latest_video = max(video_files, key=os.path.getctime)
        
        with open(latest_video, 'rb') as f:
            return f.read(), "✅ Animation generated successfully!"
            
    except Exception as e:
        logger.error(f"Video generation error: {str(e)}")
        return None, f"❌ Error: {str(e)}"
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")
# Main Streamlit UI
st.set_page_config(
    page_title="Manim Animation Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .stButton>button {
        width: 100%;
    }
    .code-editor {
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .output-video {
        border-radius: 10px;
        margin-top: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if 'video_data' not in st.session_state:
    st.session_state.video_data = None
if 'status' not in st.session_state:
    st.session_state.status = None
if 'ai_models' not in st.session_state:
    st.session_state.ai_models = None
if 'generated_code' not in st.session_state:
    st.session_state.generated_code = ""

# Ensure required packages are installed
if not ensure_packages():
    st.error("Failed to install required packages. Please try again.")
    st.stop()

st.title("🎬 Manim Animation Generator")
st.markdown("Create beautiful mathematical animations with ease!")

# Initialize AI models if needed
if st.session_state.ai_models is None:
    with st.spinner("Loading AI models..."):
        st.session_state.ai_models = init_ai_models()

# Create tabs
tab1, tab2, tab3 = st.tabs(["✨ Main", "🛠️ Assets", "🤖 AI Assistant"])

# Main Tab
with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if not TEMPLATES:
            st.error("Template data is missing")
            st.stop()
            
        template_name = st.selectbox(
            "🎨 Animation Templates",
            options=list(TEMPLATES.keys())
        )
        
        code = st.text_area(
            "📝 Manim Python Code",
            value=TEMPLATES[template_name],
            height=300,
            key="code_editor"
        )
        
        col1_1, col1_2, col1_3 = st.columns(3)
        with col1_1:
            quality = st.selectbox(
                "🎯 Quality Preset",
                options=list(QUALITY_PRESETS.keys())
            )
        with col1_2:
            format_type = st.selectbox(
                "📦 Format",
                options=["mp4", "gif"]
            )
        with col1_3:
            animation_speed = st.selectbox(
                "⚡ Speed",
                options=list(ANIMATION_SPEEDS.keys())
            )
        
        col2_1, col2_2 = st.columns(2)
        with col2_1:
            palette = st.selectbox(
                "🎨 Color Palette",
                options=list(COLOR_PALETTES.keys())
            )
            background_color = COLOR_PALETTES[palette]["background"]
        with col2_2:
            st.markdown("###")  # Spacing
            use_custom_color = st.checkbox("Custom Background Color")
            if use_custom_color:
                background_color = st.color_picker("Pick Color", background_color)
        
        if st.button("🚀 Generate Animation", type="primary"):
            if not code:
                st.error("Please enter some code before generating animation")
            else:
                with st.spinner("Generating animation..."):
                    video_data, status = generate_manim_video(
                        code, 
                        format_type, 
                        quality, 
                        background_color,
                        ANIMATION_SPEEDS[animation_speed]
                    )
                    st.session_state.video_data = video_data
                    st.session_state.status = status
    
    with col2:
        if st.session_state.video_data:
            st.video(st.session_state.video_data, format=format_type)
        if st.session_state.status:
            st.info(st.session_state.status)
# Assets Tab
with tab2:
    st.subheader("🖼️ Asset Management")
    
    uploaded_image = st.file_uploader("📸 Upload Image", type=["png", "jpg", "jpeg"])
    if uploaded_image:
        st.image(uploaded_image, caption="Uploaded Image")
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                tmp_file.write(uploaded_image.getvalue())
                tmp_path = tmp_file.name
                if st.button("Add Image to Animation"):
                    image_code = f"""
                    # Load and display image
                    image = ImageMobject("{tmp_path}")
                    self.play(FadeIn(image))
                    self.wait(1)
                    """
                    if 'code' in st.session_state:
                        st.session_state.code += image_code
                        st.experimental_rerun()
        finally:
            if 'tmp_path' in locals():
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.error(f"Failed to clean up image file: {str(e)}")

# AI Assistant Tab
with tab3:
    st.subheader("🤖 AI Animation Assistant")
    
    # Sidebar for generated code
    st.sidebar.markdown("### 📝 Generated Code")
    generated_code_box = st.sidebar.text_area(
        "Current Generated Code",
        value=st.session_state.generated_code,
        height=300,
        key="generated_code_display"
    )
    
    if st.sidebar.button("Use Generated Code"):
        if st.session_state.generated_code:
            st.session_state.code = st.session_state.generated_code
            st.rerun()
    
    if st.session_state.ai_models:
        st.write("Describe the animation you want to create, or provide partial code to complete:")
        code_input = st.text_area(
            "Your Prompt or Code",
            placeholder="Example: Create an animation that shows a circle morphing into a square while changing color from red to blue",
            height=150
        )
        
        if code_input and st.button("Generate Animation Code"):
            with st.spinner("Generating code..."):
                response = suggest_code_completion(code_input, st.session_state.ai_models)
                if response:
                    st.session_state.generated_code = response
    else:
        st.warning("AI models failed to load. Some features may be unavailable.")

# Save/Load functionality in sidebar
st.sidebar.markdown("---")
st.sidebar.title("💾 Save & Load")

if st.sidebar.button("Export Current Scene"):
    if 'code' in st.session_state:
        settings = {
            "quality": quality,
            "format": format_type,
            "palette": palette,
            "speed": animation_speed,
            "background": background_color
        }
        export_data = export_scene(st.session_state.code, settings)
        if export_data:
            st.sidebar.code(export_data, language="text")
        else:
            st.sidebar.error("Failed to export scene")

imported_data = st.sidebar.text_area("Import Scene (paste exported code)")
if st.sidebar.button("Load Scene") and imported_data:
    imported_code, imported_settings = import_scene(imported_data)
    if imported_code and imported_settings:
        st.session_state.code = imported_code
        st.experimental_rerun()
    else:
        st.sidebar.error("Failed to import scene")

# Footer
st.markdown("""
---
### 💡 Tips:
- Use the AI assistant to generate animation ideas
- Preview animations in draft quality first
- Export your scenes to save and share them
- Try combining different equations and animations
- Check the generated code box for the latest AI output
""")

st.markdown("""
---
Made with ❤️ using Streamlit and Manim | AI-Powered Animation Generator
""")

# Error handling for session state cleanup
try:
    if 'temp_files' in st.session_state:
        for file in st.session_state.temp_files:
            if os.path.exists(file):
                os.unlink(file)
        st.session_state.temp_files = []
except Exception as e:
    logger.error(f"Session cleanup error: {str(e)}")