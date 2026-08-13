import os
import sys
from pathlib import Path

# Add project root to sys.path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.project_model import ProjectCreatePayload, AddStoryPayload
from services.project_manager import create_project, add_user_story_to_project

def run_test():
    print("--- Starting Integration Test ---")
    
    # 1. Create a dummy project
    payload = ProjectCreatePayload(
        projectName="TestComplexDashboard",
        framework="React",
        language="TypeScript",
        cssStrategy="Separate",
        folderStructure="Flat"
    )
    result = create_project(payload)
    project_id = result["config"]["projectId"]
    print(f"Created Project: {project_id}")

    # 2. Add a user story using the generated wireframe
    # The agent saves generated images to the artifacts directory.
    # We will pass the path to the wireframe.
    wireframe_path = r"C:\Users\NikileshwarJagadeesa\.gemini\antigravity-ide\brain\25a19fef-0b8f-4e80-a42c-93b8429e3a88\complex_dashboard_wireframe_1786432498902.png"
    
    if not os.path.exists(wireframe_path):
        print(f"ERROR: Wireframe not found at {wireframe_path}")
        return

    story_payload = AddStoryPayload(
        userStory="Build a complex analytics dashboard with a sidebar, header, KPI cards, charts, and a data table. Must be fully responsive.",
        imagePath=wireframe_path
    )
    
    print("Running pipeline on complex wireframe...")
    try:
        response = add_user_story_to_project(project_id, story_payload, wireframe_path)
        print("\n--- Pipeline Execution Successful ---")
        print("Generated Files:")
        for f in response.get("newFilesGenerated", []):
            print(f"  - {f}")
    except Exception as e:
        print(f"\n--- Pipeline Execution Failed ---")
        print(e)
        raise e

if __name__ == "__main__":
    run_test()
