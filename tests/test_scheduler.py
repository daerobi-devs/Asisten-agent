import asyncio
import pytest
from lxion.scheduler.cron_manager import CronJobManager, JobType, parse_schedule_trigger
from lxion.memory.workspace import workspace
from lxion.tools.builtin.scheduler_tools import SendChannelMessageTool, ScheduleJobTool
from lxion.channels.bus import message_bus, ChannelType

@pytest.mark.asyncio
async def test_direct_tool_cron_job(tmp_path):
    mgr = CronJobManager(persistence_file=tmp_path / "cron_test.json")
    mgr.start()

    # 1. Add direct tool job that writes a file every 1s (NO AI / 0 tokens)
    job = mgr.add_job(
        name="test_direct_heartbeat",
        schedule_type="interval",
        schedule_value="1s",
        job_type=JobType.DIRECT_TOOL,
        target="write_file",
        parameters={"path": "cron_heartbeat.txt", "content": "cron alive"}
    )
    assert job["job_type"] == "direct_tool"
    assert len(mgr.list_jobs()) == 1

    # Wait 2 seconds for trigger
    await asyncio.sleep(2.2)

    # Verify file was written by cron
    content = workspace.read_file("cron_heartbeat.txt")
    assert content == "cron alive"

    # Check history
    history = mgr.get_history()
    assert len(history) >= 1
    assert history[-1]["status"] == "success"

    # Remove job
    removed = mgr.remove_job(job["id"])
    assert removed is True
    mgr.stop()

def test_schedule_trigger_parsing():
    # 1. Daily
    trig_daily = parse_schedule_trigger("daily", "07:00")
    assert trig_daily is not None

    # 2. Weekly with Indonesian days
    trig_weekly_id = parse_schedule_trigger("weekly", "senin,selasa,rabu@07:00")
    assert trig_weekly_id is not None

    # 3. Weekly with English days
    trig_weekly_en = parse_schedule_trigger("weekly", "mon,wed,fri@08:30")
    assert trig_weekly_en is not None

    # 4. Specific Date
    trig_date = parse_schedule_trigger("date", "2026-12-31 23:59:59")
    assert trig_date is not None

    # 5. Standard Cron
    trig_cron = parse_schedule_trigger("cron", "0 7 * * 1-5")
    assert trig_cron is not None

@pytest.mark.asyncio
async def test_job_metadata_and_channel_routing(tmp_path):
    mgr = CronJobManager(persistence_file=tmp_path / "cron_meta_test.json")
    mgr.start()

    # Schedule a weekly class schedule reminder for Monday at 07:00 targeting Telegram
    job = mgr.add_job(
        name="Jadwal Kuliah Senin",
        schedule_type="weekly",
        schedule_value="senin@07:00",
        job_type=JobType.DIRECT_TOOL,
        target="send_channel_message",
        channel="telegram",
        agent_id="lxion_core",
        parameters={"channel": "telegram", "message": "Waktunya kuliah Algoritma!"}
    )

    assert job["channel"] == "telegram"
    assert job["agent_id"] == "lxion_core"
    assert job["schedule_type"] == "weekly"

    # List jobs
    all_jobs = mgr.list_jobs()
    assert len(all_jobs) == 1
    assert all_jobs[0]["channel"] == "telegram"
    assert all_jobs[0]["agent_id"] == "lxion_core"

    # Schedule AI prompt for sosmed specialist every 5 hours
    job2 = mgr.add_job(
        name="Sosmed Trending Ideation",
        schedule_type="interval",
        schedule_value="5h",
        job_type=JobType.AI_PROMPT,
        target="Cari 3 topik viral AI dan buat draft tweet",
        channel="telegram",
        agent_id="sosmed_specialist"
    )

    assert job2["agent_id"] == "sosmed_specialist"
    assert len(mgr.list_jobs()) == 2

    mgr.remove_job(job["id"])
    mgr.remove_job(job2["id"])
    assert len(mgr.list_jobs()) == 0
    mgr.stop()

@pytest.mark.asyncio
async def test_send_channel_message_tool():
    tool = SendChannelMessageTool()
    captured_messages = []

    async def mock_sender(msg):
        captured_messages.append(msg)

    message_bus.register_channel_sender(ChannelType.TELEGRAM, mock_sender)

    res = await tool.execute(channel="telegram", message="Halo dari 0-token tool!", recipient_id="12345")
    assert res["success"] is True
    assert len(captured_messages) == 1
    assert captured_messages[0].text == "Halo dari 0-token tool!"
    assert captured_messages[0].recipient_id == "12345"

@pytest.mark.asyncio
async def test_schedule_job_tool():
    tool = ScheduleJobTool()
    res = await tool.execute(
        name="Kuliah Test",
        schedule_type="daily",
        schedule_value="07:00",
        job_type="direct_tool",
        target="send_channel_message",
        channel="telegram",
        agent_id="lxion_core"
    )
    assert res["success"] is True
    assert res["job"]["name"] == "Kuliah Test"
    assert res["job"]["channel"] == "telegram"

    # Cleanup
    from lxion.scheduler.cron_manager import cron_manager
    cron_manager.remove_job(res["job"]["id"])
