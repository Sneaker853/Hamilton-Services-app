import logging
import sys

from config import PROJECT_ROOT, DATABASE_URL

sys.path.insert(0, str(PROJECT_ROOT / "portfolio_app"))

from config_manager import ConfigManager
from engine_core import PortfolioBuilder

logger = logging.getLogger(__name__)

config_manager: ConfigManager | None = None
portfolio_builder: PortfolioBuilder | None = None


def initialize_services() -> None:
    global config_manager, portfolio_builder

    if config_manager is None:
        config_manager = ConfigManager()
    if portfolio_builder is None:
        portfolio_builder = PortfolioBuilder(DATABASE_URL, config_manager)

    logger.info("Services initialized successfully")


def get_config_manager() -> ConfigManager:
    if config_manager is None:
        raise RuntimeError("Config manager not initialized")
    return config_manager


def get_portfolio_builder() -> PortfolioBuilder:
    if portfolio_builder is None:
        raise RuntimeError("Portfolio builder not initialized")
    return portfolio_builder
