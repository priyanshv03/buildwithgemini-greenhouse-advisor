# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from pathlib import Path

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import (
    AgentEngineSandboxCodeExecutor,
)
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.a2ui_utils import a2ui_callback
from app.tools import (
    add_or_update_plant,
    check_local_weather,
    find_nearby_places,
    generate_plant_image,
    generate_plant_video,
    geocode_address,
    get_plant_details,
    list_greenhouse_plants,
    log_watering_event,
    lookup_botanical_taxonomy,
)

# Build A2UI System Prompt using A2uiSchemaManager (version 0.8) and BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are an expert Plant-Care & Greenhouse Advisor assistant. "
        "You continuously remember, track, and recall all user allergies (such as pollen, plant sap, latex, mold, specific plant species, or chemical sensitivities) and plant favorable conditions stated or requested by the user across conversations. "
        "Always cross-check plant recommendations, care advice, and nursery suggestions against the user's remembered allergies to keep them safe and avoid recommending allergen-triggering plants."
    ),
    workflow_description=(
        "Analyze the request, use appropriate tools to query plant data/weather/taxonomy/nurseries or execute calculations, "
        "and return structured A2UI UI when appropriate."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

# Load Agent Engine resource name from deployment_metadata.json if present
metadata_path = Path(__file__).parent.parent / "deployment_metadata.json"
agent_engine_resource_name = None
memory_bank_id = None

if metadata_path.exists():
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
            if agent_engine_resource_name:
                memory_bank_id = agent_engine_resource_name.split("/")[-1]
    except Exception:
        pass

# Fallback memory bank ID if not found in metadata
if not memory_bank_id:
    memory_bank_id = "2369105609741041664"

# WRITE: Callback to send session events to Memory Bank after each turn
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None

# Memory service builder for deployed Agent Runtime instances
def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project="qwiklabs-gcp-01-bff06e314e48",
        location="us-east1",
        agent_engine_id=memory_bank_id,
    )

# Instantiate AgentEngineSandboxCodeExecutor using the Agent Engine resource ID
code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        list_greenhouse_plants,
        get_plant_details,
        add_or_update_plant,
        log_watering_event,
        check_local_weather,
        lookup_botanical_taxonomy,
        geocode_address,
        find_nearby_places,
        generate_plant_image,
        generate_plant_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
