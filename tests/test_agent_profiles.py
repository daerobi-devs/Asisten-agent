import pytest
from pathlib import Path
from lxion.agents.profile_store import AgentProfile, AgentProfileStore
from lxion.agents.agent_factory import (
    CreateAgentProfileTool, UpdateAgentProfileTool,
    ListAgentProfilesTool, DeleteAgentProfileTool
)
from lxion.core.agent import Agent
from lxion.tools.registry import registry

@pytest.fixture
def temp_store(tmp_path):
    store_file = tmp_path / "test_profiles.json"
    return AgentProfileStore(store_file=store_file)

def test_store_seeding_and_primary_protection(temp_store):
    profiles = temp_store.list_profiles()
    assert len(profiles) >= 2
    
    primary = temp_store.get_profile("lxion_core")
    assert primary is not None
    assert primary.is_primary is True
    assert primary.provider == "9router"
    assert primary.model == "wkwk"

    # Attempting to delete primary should raise ValueError
    with pytest.raises(ValueError, match="Primary Agent"):
        temp_store.delete_profile("lxion_core")

def test_store_whatsapp_exclusivity(temp_store):
    # Try creating sub-agent with WhatsApp binding
    sub = AgentProfile(
        id="rogue_bot",
        name="Rogue Bot",
        description="Testing WhatsApp hijacking block",
        provider="9router",
        model="wkwk",
        channel_bindings={"whatsapp": True, "discord_token": "disc123"}
    )
    saved = temp_store.save_profile(sub)
    # WhatsApp should be stripped automatically
    assert "whatsapp" not in saved.channel_bindings
    assert saved.channel_bindings.get("discord_token") == "disc123"
    assert saved.is_primary is False

def test_agent_factory_tools(temp_store):
    import lxion.agents.agent_factory as af
    old_store = af.profile_store
    af.profile_store = temp_store

    try:
        create_tool = CreateAgentProfileTool()
        update_tool = UpdateAgentProfileTool()
        list_tool = ListAgentProfilesTool()
        delete_tool = DeleteAgentProfileTool()

        import asyncio
        # 1. Create
        res = asyncio.run(create_tool.execute(
            id="coding_specialist",
            name="Coding Specialist",
            description="Expert Python and Rust engineer",
            soul_prompt="You write pristine code with zero defects.",
            provider="openai",
            model="gpt-4o",
            assigned_tools=["read_file", "write_file", "run_code"],
            assigned_skills=["taste-skill"]
        ))
        assert res["success"] is True
        assert res["profile"]["id"] == "coding_specialist"
        assert res["profile"]["provider"] == "openai"
        assert res["profile"]["model"] == "gpt-4o"
        assert len(res["profile"]["assigned_tools"]) == 3

        # 2. List
        list_res = asyncio.run(list_tool.execute())
        ids = [p["id"] for p in list_res]
        assert "coding_specialist" in ids

        # 3. Update
        up_res = asyncio.run(update_tool.execute(
            id="coding_specialist",
            name="Senior Coding Specialist",
            model="o3-mini"
        ))
        assert up_res["success"] is True
        assert up_res["profile"]["name"] == "Senior Coding Specialist"
        assert up_res["profile"]["model"] == "o3-mini"

        # 4. Delete
        del_res = asyncio.run(delete_tool.execute(id="coding_specialist"))
        assert del_res["success"] is True
        assert temp_store.get_profile("coding_specialist") is None

    finally:
        af.profile_store = old_store

def test_agent_tool_and_prompt_gating():
    # Primary agent with taste-skill
    primary_profile = AgentProfile(
        id="lxion_core",
        name="LXION Core",
        soul_prompt="LXION Root Identity",
        assigned_tools=["*"],
        assigned_skills=["taste-skill"],
        is_primary=True
    )
    primary_agent = Agent(profile=primary_profile)
    assert "LXION Root Identity" in primary_agent.system_prompt
    assert "Taste Skill" in primary_agent.system_prompt

    # Sub-agent with minimal tools and no taste-skill
    sub_profile = AgentProfile(
        id="light_searcher",
        name="Light Searcher",
        soul_prompt="You only search the web.",
        assigned_tools=["fetch_url"],
        assigned_skills=[],
        is_primary=False
    )
    sub_agent = Agent(profile=sub_profile)
    assert "Taste Skill" not in sub_agent.system_prompt
    assert "You only search the web." in sub_agent.system_prompt

    # Filtered tools in registry
    filtered_tools = registry.get_openai_tools(sub_profile.assigned_tools)
    assert len(filtered_tools) == 1
    assert filtered_tools[0]["function"]["name"] == "fetch_url"
