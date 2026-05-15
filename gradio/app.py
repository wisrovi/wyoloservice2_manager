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

        study_name = config.get('sweeper', {}).get('study_name', 'unknown')
        priority = config.get('sweeper', {}).get('priority', 'low')

        # Send the task to the manager
        result = app.send_task("tasks.manage_study", args=[config], queue="managers")
        
        return (f"✅ Study launched successfully!\n\n"
                f"ID: {result.id}\n"
                f"Study Name: {study_name}\n"
                f"Priority: {priority}\n\n"
                f"The Manager is now orchestrating your trials with Optuna.\n"
                f"Check logs with: docker logs wyolo_manager -f")
    
    except Exception as e:
        return f"❌ Error launching study: {str(e)}"

# Create the Gradio interface
with gr.Blocks(title="Wyolo Study Orchestrator") as demo:
    gr.Markdown("# 🚀 Wyolo Study Orchestrator")
    gr.Markdown("Upload your search space to start the hyperparameter optimization (Optuna).")
    
    with gr.Row():
        with gr.Column():
            file_input = gr.File(label="Upload Configuration (YAML)", file_types=[".yaml", ".yml"])
            launch_btn = gr.Button("🚀 Launch Optimization Study", variant="primary")
        
        with gr.Column():
            output_text = gr.Textbox(label="Status / Orchestration Details", interactive=False, lines=10)
    
    launch_btn.click(
        fn=launch_study,
        inputs=file_input,
        outputs=output_text
    )
    
    gr.Markdown("### 📝 Example YAML structure:")
    gr.Code(
        value="""model: "yolov8n-cls.pt"
type: "yolo"
train:
  epochs: 5
  imgsz: 640
sweeper:
  study_name: "color_ball_v3"
  direction: "maximize"
  fitness: "metrics/accuracy_top1"
  n_trials: 10
  priority: "high"  # Choices: high, medium, low
  search_space:
    train:
      lr0: ["loguniform", 1e-5, 1e-2]
      imgsz: ["choice", 416, 640]""",
        language="yaml"
    )

if __name__ == "__main__":
    # Get port from environment or default to 7860
    port = int(os.getenv("GRADIO_PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
