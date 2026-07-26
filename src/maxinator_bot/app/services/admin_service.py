from maxinator_bot.app.config import Settings


class AdminService:
    def __init__(self, settings: Settings) -> None:
        self._admin_ids = settings.admin_max_ids

    def is_admin(self, max_user_id: str) -> bool:
        return str(max_user_id) in self._admin_ids
