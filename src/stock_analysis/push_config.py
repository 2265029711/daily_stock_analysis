# -*- coding: utf-8 -*-
"""
===================================
多用户推送配置模块（push_config.yaml）
===================================

职责：
1. 从 push_config.yaml 加载多用户 Bark 推送配置
2. 支持 ${ENV} 占位符引用环境变量（本地 .env / GitHub Actions secrets）
3. 校验用户配置合法性（股票代码须在全局 STOCK_LIST 内）

配置示例：
    users:
      - name: 用户A-大盘
        device_key: ${BARK_KEY_USER_A}
        group: 大盘走势
        push_market: true          # 接收大盘复盘
        stocks: []                 # 不接收个股
      - name: 用户B-个股
        device_key: ${BARK_KEY_USER_B}
        group: 个股分析
        push_market: false
        stocks: [600519, 300750]   # 指定个股；all = 全部
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml

from stock_analysis.config import get_config

logger = logging.getLogger(__name__)

# 项目根目录（src/stock_analysis/ 上两级）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 默认配置文件路径
DEFAULT_CONFIG_PATH = PROJECT_ROOT / 'push_config.yaml'

# ${ENV_NAME} 占位符
_ENV_PATTERN = re.compile(r'\$\{([^}]+)\}')


@dataclass
class PushUser:
    """单个推送用户配置"""
    name: str
    device_key: str = ""
    server_url: Optional[str] = None   # 可选，默认使用 .env 的 BARK_SERVER_URL
    group: str = "股票分析"
    push_market: bool = False          # 是否接收大盘复盘
    stocks: List[str] = field(default_factory=list)  # 接收的个股列表；空 = 不接收个股
    all_stocks: bool = False           # stocks: all 时接收全部自选股

    @property
    def wants_stocks(self) -> bool:
        """是否需要个股推送"""
        return self.all_stocks or bool(self.stocks)

    @property
    def is_valid(self) -> bool:
        """设备 Key 解析后是否有效"""
        return bool(self.device_key)


def _resolve_env(text: str, missing: List[str]) -> str:
    """替换 ${ENV} 占位符为环境变量值"""
    if not text or '${' not in text:
        return text

    def repl(m: re.Match) -> str:
        env_name = m.group(1)
        value = os.environ.get(env_name)
        if value is None:
            missing.append(env_name)
            return ""
        return value

    return _ENV_PATTERN.sub(repl, text)


class PushConfig:
    """
    多用户推送配置
    
    从 push_config.yaml 加载，提供：
    - users: 用户列表
    - is_configured: 是否存在有效配置
    - get_user_stocks(user): 解析用户对应的股票列表
    """

    def __init__(self, users: List[PushUser]):
        self.users = users

    @property
    def is_configured(self) -> bool:
        """是否存在至少一个有效用户"""
        return any(u.is_valid for u in self.users)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> 'PushConfig':
        """
        加载多用户配置
        
        Args:
            path: 配置文件路径（默认项目根 push_config.yaml）
            
        Returns:
            PushConfig 对象（文件不存在或格式错误时返回空配置）
        """
        # 确保 .env 已加载（独立使用 push_config 时也能解析 ${ENV} 占位符）
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=PROJECT_ROOT / '.env')
        except ImportError:
            pass

        path = Path(path) if path else DEFAULT_CONFIG_PATH

        if not path.exists():
            logger.info(f"未找到推送配置文件 {path}，跳过多用户推送")
            return cls([])

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"解析推送配置文件 {path} 失败: {e}")
            return cls([])

        if not data or not isinstance(data, dict) or 'users' not in data:
            logger.warning(f"推送配置文件 {path} 缺少 users 字段")
            return cls([])

        users = []
        missing_envs: List[str] = []
        for i, item in enumerate(data.get('users', [])):
            if not isinstance(item, dict):
                logger.warning(f"[用户配置 #{i}] 配置项格式错误，跳过")
                continue

            name = str(item.get('name', f'用户{i + 1}'))
            device_key = _resolve_env(str(item.get('device_key', '')), missing_envs).strip()
            server_url = _resolve_env(str(item.get('server_url', '')), missing_envs).strip() or None

            stocks_raw = item.get('stocks', [])
            all_stocks = isinstance(stocks_raw, str) and stocks_raw.lower() == 'all'
            if all_stocks:
                stocks: List[str] = []
            elif isinstance(stocks_raw, list):
                # 股票代码按字符串读取（配置中必须用引号包裹，如 '000725'）
                stocks = [str(s).strip() for s in stocks_raw if str(s).strip()]
            else:
                stocks = []

            users.append(PushUser(
                name=name,
                device_key=device_key,
                server_url=server_url,
                group=str(item.get('group', '股票分析')),
                push_market=bool(item.get('push_market', False)),
                stocks=stocks,
                all_stocks=all_stocks,
            ))

        if missing_envs:
            logger.warning(f"以下环境变量未配置（占位符无法解析）: {', '.join(set(missing_envs))}")

        # 过滤无效用户（device_key 为空）
        valid_users = [u for u in users if u.is_valid]
        invalid_count = len(users) - len(valid_users)
        if invalid_count:
            logger.warning(f"有 {invalid_count} 个用户因设备 Key 无效被跳过")

        return cls(valid_users)

    def get_user_stocks(self, user: PushUser, all_stocks: List[str]) -> List[str]:
        """
        解析用户接收的股票列表
        
        Args:
            user: 用户配置
            all_stocks: 全局自选股列表（STOCK_LIST）
            
        Returns:
            用户可见的股票代码列表（stocks: all 时返回全局列表）
        """
        if user.all_stocks:
            return list(all_stocks)
        return list(user.stocks)

    def get_requested_stocks(self, all_stocks: List[str]) -> List[str]:
        """
        汇总所有用户配置中要求的股票代码
        
        用户指定的股票会自动纳入分析范围（不限于全局 STOCK_LIST）
        
        Args:
            all_stocks: 全局自选股列表（STOCK_LIST）
            
        Returns:
            去重后的股票代码列表
        """
        requested: List[str] = []
        for user in self.users:
            for code in self.get_user_stocks(user, all_stocks):
                if code not in requested:
                    requested.append(code)
        return requested

    def validate(self, all_stocks: List[str]) -> List[str]:
        """
        校验用户配置
        
        Returns:
            警告列表
        """
        warnings = []
        for user in self.users:
            for code in user.stocks:
                # 只校验代码格式（沪深 A 股 6 位数字）
                if not code.isdigit() or len(code) != 6:
                    warnings.append(
                        f"[用户 {user.name}] 股票代码格式不正确（应为 6 位数字）: {code}"
                    )
            if user.push_market and not user.wants_stocks:
                warnings.append(f"[用户 {user.name}] 只接收大盘复盘（push_market=true, stocks 为空）")
        return warnings


# 便捷函数
def get_push_config(path: Optional[Path] = None) -> PushConfig:
    """获取多用户推送配置"""
    return PushConfig.load(path)
