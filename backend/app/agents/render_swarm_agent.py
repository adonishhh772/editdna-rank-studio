from pathlib import Path

from app.agents.base import BaseAgent
from app.blackboard import ProjectBlackboard
from app.constants.render_pipeline import (
    AUDIO_MIX_REQUEST_KEY,
    HOOK_OVERLAY_REQUEST_KEY,
    RANK_CLIP_RENDER_REQUEST_KEY,
    RENDER_OUTPUT_PATH_KEY,
    RENDER_PROCESSED_CLIPS_KEY,
    RENDER_STAGE_AUDIO,
    RENDER_STAGE_HOOK,
    RENDER_STAGE_STITCH,
    RENDER_STAGE_TRIM,
    VIDEO_STITCH_REQUEST_KEY,
)
from app.schemas import RankedClip
from app.services.render_pipeline import (
    apply_hook_overlay,
    finalize_render_output,
    render_project_dir,
    render_rank_clip,
    stitch_rank_clips,
)
from app.services.video_utils import get_video_duration


class RankClipRenderAgent(BaseAgent):
    agent_id = "rank_clip_render"
    agent_name = "Rank Clip Render"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        request = blackboard.memory_context.get(RANK_CLIP_RENDER_REQUEST_KEY, {})
        section_data = request.get("section")
        index = int(request.get("index", 0))
        caption_font_size = int(request.get("caption_font_size") or 48)
        if not isinstance(section_data, dict):
            raise RuntimeError("Rank clip render request is missing section data")

        section = RankedClip.model_validate(section_data)
        project_dir = Path(str(request.get("project_dir")))

        trace = self.active_trace(blackboard)
        trace.input_summary = f"Rendering rank #{section.rank}: {section.video_moment_title or section.label_text}"
        trace.visible_reasoning = (
            f"Trimming {section.clip_start_sec:.1f}s–{section.clip_end_sec:.1f}s, "
            f"scaling to 9:16, adding rank overlay"
        )

        labeled_path = await render_rank_clip(section, index, project_dir, caption_font_size=caption_font_size)
        processed_clips = blackboard.memory_context.get(RENDER_PROCESSED_CLIPS_KEY)
        if not isinstance(processed_clips, list):
            processed_clips = []
        processed_clips.append(labeled_path)
        blackboard.memory_context[RENDER_PROCESSED_CLIPS_KEY] = processed_clips

        self.log_tool_call(
            blackboard,
            "render_pipeline",
            {
                "stage": RENDER_STAGE_TRIM,
                "rank": section.rank,
                "local_file_path": labeled_path,
            },
        )
        trace.output_summary = f"Rank #{section.rank} clip ready"
        return blackboard


class VideoStitchAgent(BaseAgent):
    agent_id = "video_stitch"
    agent_name = "Video Stitch"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        request = blackboard.memory_context.get(VIDEO_STITCH_REQUEST_KEY, {})
        clips = request.get("clips")
        project_dir = Path(str(request.get("project_dir")))
        if not isinstance(clips, list) or not clips:
            raise RuntimeError("Video stitch request is missing clips")

        trace = self.active_trace(blackboard)
        trace.input_summary = f"Stitching {len(clips)} rank clips"
        trace.visible_reasoning = "Concatenating ranked clips into one timeline"

        concat_path = await stitch_rank_clips(clips, project_dir)
        blackboard.memory_context[VIDEO_STITCH_REQUEST_KEY] = {
            **request,
            "concat_path": concat_path,
        }
        self.log_tool_call(
            blackboard,
            "render_pipeline",
            {"stage": RENDER_STAGE_STITCH, "local_file_path": concat_path},
        )
        trace.output_summary = "Rank clips stitched"
        return blackboard


class HookOverlayAgent(BaseAgent):
    agent_id = "hook_overlay"
    agent_name = "Hook Overlay"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        request = blackboard.memory_context.get(HOOK_OVERLAY_REQUEST_KEY, {})
        source_path = str(request.get("source_path") or "")
        hook_text = str(request.get("hook_text") or "")
        output_duration_sec = float(request.get("output_duration_sec") or 0.0)
        project_dir = Path(str(request.get("project_dir")))
        caption_font_size = int(request.get("caption_font_size") or 48)
        if not source_path:
            raise RuntimeError("Hook overlay request is missing source path")

        trace = self.active_trace(blackboard)
        trace.input_summary = "Adding opening hook overlay"
        trace.visible_reasoning = f'Applying hook text: "{hook_text[:60]}"'

        with_hook = await apply_hook_overlay(
            source_path,
            hook_text,
            output_duration_sec,
            project_dir,
            caption_font_size=caption_font_size,
        )
        blackboard.memory_context[HOOK_OVERLAY_REQUEST_KEY] = {
            **request,
            "with_hook_path": with_hook,
        }
        self.log_tool_call(
            blackboard,
            "render_pipeline",
            {"stage": RENDER_STAGE_HOOK, "local_file_path": with_hook},
        )
        trace.output_summary = "Hook overlay applied"
        return blackboard


class AudioMixAgent(BaseAgent):
    agent_id = "audio_mix"
    agent_name = "Audio Mix"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        request = blackboard.memory_context.get(AUDIO_MIX_REQUEST_KEY, {})
        source_path = str(request.get("source_path") or "")
        voiceover_path = request.get("voiceover_path")
        project_id = str(request.get("project_id") or "")
        version = int(request.get("version") or 1)
        audio_plan = request.get("audio_plan")
        if not isinstance(audio_plan, dict):
            audio_plan = {}
        if not source_path:
            raise RuntimeError("Audio mix request is missing source path")

        trace = self.active_trace(blackboard)
        if voiceover_path and Path(str(voiceover_path)).exists():
            trace.input_summary = "Mixing voiceover with clip audio"
            mix_mode = audio_plan.get("mix_mode", "balanced")
            trace.visible_reasoning = (
                f"Reference-driven mix ({mix_mode}): weighting voiceover vs source audio"
            )
        else:
            trace.input_summary = "Finalizing rendered video"
            trace.visible_reasoning = "No voiceover track — exporting stitched video"

        output_path = await finalize_render_output(
            source_path=source_path,
            voiceover_path=str(voiceover_path) if voiceover_path else None,
            project_id=project_id,
            version=version,
            audio_plan=audio_plan,
        )
        blackboard.memory_context[RENDER_OUTPUT_PATH_KEY] = output_path
        self.log_tool_call(
            blackboard,
            "render_pipeline",
            {"stage": RENDER_STAGE_AUDIO, "local_file_path": output_path},
        )
        trace.output_summary = f"Final video exported ({Path(output_path).name})"
        return blackboard


class RenderSwarmAgent(BaseAgent):
    agent_id = "render_swarm"
    agent_name = "Render Swarm"

    async def run(self, blackboard: ProjectBlackboard) -> ProjectBlackboard:
        edit_plan = blackboard.edit_plan
        if edit_plan is None:
            raise RuntimeError("Edit plan is required for rendering")

        parent_trace = self.active_trace(blackboard)
        parent_agent_id = self.agent_id
        project_dir = render_project_dir(edit_plan.project_id, edit_plan.version)
        voiceover_path = edit_plan.audio_plan.get("voiceover_path")
        render_settings = edit_plan.render_settings if isinstance(edit_plan.render_settings, dict) else {}
        caption_font_size = int(render_settings.get("caption_font_size") or 48)
        sub_agents: list[str] = []

        blackboard.memory_context.pop(RENDER_PROCESSED_CLIPS_KEY, None)
        blackboard.memory_context.pop(RENDER_OUTPUT_PATH_KEY, None)

        rank_agent = RankClipRenderAgent()
        for index, section in enumerate(edit_plan.sections):
            blackboard.memory_context[RANK_CLIP_RENDER_REQUEST_KEY] = {
                "section": section.model_dump(),
                "index": index,
                "project_dir": str(project_dir),
                "caption_font_size": caption_font_size,
            }
            blackboard = await rank_agent.execute(
                blackboard,
                parent_agent_id=parent_agent_id,
                swarm=True,
            )
            sub_agents.append(RankClipRenderAgent.agent_id)

        processed_clips = blackboard.memory_context.get(RENDER_PROCESSED_CLIPS_KEY, [])
        if not isinstance(processed_clips, list) or not processed_clips:
            raise RuntimeError("No rank clips were rendered")

        stitch_agent = VideoStitchAgent()
        blackboard.memory_context[VIDEO_STITCH_REQUEST_KEY] = {
            "clips": processed_clips,
            "project_dir": str(project_dir),
        }
        blackboard = await stitch_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )
        sub_agents.append(VideoStitchAgent.agent_id)

        stitch_result = blackboard.memory_context.get(VIDEO_STITCH_REQUEST_KEY, {})
        concat_path = stitch_result.get("concat_path") if isinstance(stitch_result, dict) else None
        if not concat_path:
            raise RuntimeError("Stitched video path is missing")

        hook_agent = HookOverlayAgent()
        blackboard.memory_context[HOOK_OVERLAY_REQUEST_KEY] = {
            "source_path": concat_path,
            "hook_text": edit_plan.hook_text,
            "output_duration_sec": edit_plan.output_duration_sec,
            "project_dir": str(project_dir),
            "caption_font_size": caption_font_size,
        }
        blackboard = await hook_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )
        sub_agents.append(HookOverlayAgent.agent_id)

        hook_result = blackboard.memory_context.get(HOOK_OVERLAY_REQUEST_KEY, {})
        with_hook_path = hook_result.get("with_hook_path") if isinstance(hook_result, dict) else None
        if not with_hook_path:
            raise RuntimeError("Hook overlay output is missing")

        audio_agent = AudioMixAgent()
        blackboard.memory_context[AUDIO_MIX_REQUEST_KEY] = {
            "source_path": with_hook_path,
            "voiceover_path": voiceover_path,
            "project_id": edit_plan.project_id,
            "version": edit_plan.version,
            "audio_plan": edit_plan.audio_plan,
        }
        blackboard = await audio_agent.execute(
            blackboard,
            parent_agent_id=parent_agent_id,
            swarm=True,
        )
        sub_agents.append(AudioMixAgent.agent_id)

        output_path = blackboard.memory_context.get(RENDER_OUTPUT_PATH_KEY)
        if not isinstance(output_path, str) or not output_path:
            raise RuntimeError("Rendered output path is missing")

        duration = await get_video_duration(output_path)
        edit_plan.output_duration_sec = duration
        blackboard.output_video_path = output_path
        blackboard.stage = "rendered"

        for request_key in (
            RANK_CLIP_RENDER_REQUEST_KEY,
            RENDER_PROCESSED_CLIPS_KEY,
            VIDEO_STITCH_REQUEST_KEY,
            HOOK_OVERLAY_REQUEST_KEY,
            AUDIO_MIX_REQUEST_KEY,
        ):
            blackboard.memory_context.pop(request_key, None)

        parent_trace.input_summary = f"Render swarm for {len(edit_plan.sections)} rank clips"
        parent_trace.output_summary = f"Video rendered to {Path(output_path).name}"
        parent_trace.visible_reasoning = (
            "Swarm trimmed, scaled, captioned, stitched, and mixed the final ranking video."
        )
        parent_trace.metadata["sub_agents"] = sub_agents
        parent_trace.metadata["swarm"] = True
        parent_trace.metadata["clip_count"] = len(edit_plan.sections)
        return blackboard
