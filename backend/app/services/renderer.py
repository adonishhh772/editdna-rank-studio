from app.schemas import EditPlan
from app.services.render_pipeline import render_edit_plan


class VideoRenderer:
    async def render(self, edit_plan: EditPlan, voiceover_path: str | None = None) -> str:
        return await render_edit_plan(edit_plan, voiceover_path)
