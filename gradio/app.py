import gradio as gr
import yaml
import os

# Absolute import from the package
from src.celery_config import app

def launch_study(yaml_file):
    if yaml_file is None:
        return "Please upload a YAML configuration file."
    
    try:
        # Load the configuration from the uploaded file
        with open(yaml_file.name, 'r') as f:
            config = yaml.safe_load(f)
        
        if not config:
            return "The YAML file is empty."

        # Send the task to the manager
        # The task name must match the one defined in user_orchestrator.py
        result = app.send_task("tasks.manage_study", args=[config], queue="managers")
        
        return f"Study launched successfully!\nTask ID: {result.id}\n\nYou can monitor the progress in the manager logs."
    
    except Exception as e:
        return f"Error launching study: {str(e)}"

# Create the Gradio interface
with gr.Blocks(title="Wyolo Study Orchestrator") as demo:
    gr.Markdown("# 🚀 Wyolo Study Orchestrator")
    gr.Markdown("Upload your search space and study configuration in YAML format to start the optimization process.")
    
    with gr.Row():
        with gr.Column():
            file_input = gr.File(label="Upload Search Space (YAML)", file_types=[".yaml", ".yml"])
            launch_btn = gr.Button("Launch Optimization Study", variant="primary")
        
        with gr.Column():
            output_text = gr.Textbox(label="Status / Result", interactive=False, lines=10)
    
    launch_btn.click(
        fn=launch_study,
        inputs=file_input,
        outputs=output_text
    )
    
    gr.Markdown("### Example YAML structure:")
    gr.Code(
        value="""sweeper:
  study_name: "my_optimization_study"
  direction: "maximize"
  n_trials: 10
  target_worker_queue: "gpus"
  search_space:
    model: ["choice", "yolov8n", "yolo11s"]
    train:
      lr0: ["loguniform", 1e-5, 1e-2]
      imgsz: ["range", 320, 640, 32]""",
        language="yaml"
    )

if __name__ == "__main__":
    # Get port from environment or default to 7860
    port = int(os.getenv("GRADIO_PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
