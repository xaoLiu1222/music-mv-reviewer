"""CLI entry point for MV content review."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, List

from .config import Config, get_client, get_model
from .mv_reviewer import MVReviewer
from .clients.ollama import OllamaClient
from .clients.generic_openai_api import GenericOpenAIAPIClient


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """Configure logging.

    Args:
        level: Log level string
        log_file: Optional log file path
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True
    )


def create_llm_client(config: Config):
    """Create LLM client based on configuration.

    Args:
        config: Configuration object

    Returns:
        LLM client instance or None
    """
    try:
        client_type = config.get("clients", {}).get("default", "ollama")
        client_config = get_client(config)

        if client_type == "ollama":
            return OllamaClient(client_config["url"])
        elif client_type == "openai_api":
            return GenericOpenAIAPIClient(
                client_config["api_key"],
                client_config["api_url"]
            )
        else:
            logging.warning(f"Unknown client type: {client_type}")
            return None

    except Exception as e:
        logging.warning(f"Could not create LLM client: {e}")
        return None


def load_review_config(config_path: Optional[str] = None) -> dict:
    """Load review-specific configuration.

    Args:
        config_path: Path to review config file

    Returns:
        Configuration dictionary
    """
    default_config = {
        'rules': {
            'metadata': {
                'enabled': True,
                'blocked_creators': ['林夕']
            },
            'aspect': {
                'enabled': True,
                'black_threshold': 15,
                'border_ratio': 0.05
            },
            'volume': {
                'enabled': True,
                'change_threshold_db': 10.0,
                'segment_duration_ms': 1000
            },
            'content': {
                'enabled': True,
                'confidence_threshold': 0.7
            }
        }
    }

    if config_path:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Merge with defaults
                for key, value in user_config.items():
                    if isinstance(value, dict) and key in default_config:
                        default_config[key].update(value)
                    else:
                        default_config[key] = value
        except Exception as e:
            logging.warning(f"Could not load review config: {e}")

    return default_config


# 默认LLM配置 (硅基流动)
DEFAULT_LLM_CONFIG = {
    'api_url': 'https://api.siliconflow.cn/v1',
    'model': 'Qwen/Qwen2-VL-72B-Instruct'
}


def main():
    """Main entry point for mv-reviewer CLI."""
    parser = argparse.ArgumentParser(
        description="MV内容审核工具 - 检测音乐MV中的违规内容",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 审核单个视频 (需要先设置API密钥)
  mv-reviewer video.ts --api-key "你的硅基流动API密钥"

  # 批量审核目录
  mv-reviewer ./mv_folder/ --api-key "sk-xxx" --report report.json

  # 仅检查规则1-3 (不需要LLM)
  mv-reviewer video.ts --rules 1 2 3

  # 试运行 (只检测不移动)
  mv-reviewer video.ts --api-key "sk-xxx" --dry-run

规则说明:
  1 - 作词作曲检测 (林夕等黑名单创作者)
  2 - 竖屏/黑边检测 (黑边总占比>=40%)
  3 - 音量突变检测
  4 - 暴露/导向问题检测 (需要LLM)
  5 - 纯风景背景检测 (需要LLM)
  6 - 广告内容检测 (需要LLM)
  7 - 吸毒画面检测 (需要LLM)

支持格式: .ts, .mp4, .mkv, .avi, .mov, .wmv, .flv, .webm
        """
    )

    # Positional arguments
    parser.add_argument(
        "input",
        type=str,
        help="视频文件或目录路径"
    )

    # Output options
    parser.add_argument(
        "--violation-dir",
        type=str,
        default="violations",
        help="违规视频移动目录 (默认: violations)"
    )
    parser.add_argument(
        "--report",
        type=str,
        help="输出审核报告路径 (JSON格式)"
    )

    # Rule selection
    parser.add_argument(
        "--rules",
        nargs="+",
        type=int,
        choices=[1, 2, 3, 4, 5, 6, 7],
        help="指定检查的规则 (1-7)"
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=str,
        default="config",
        help="video-analyzer配置目录"
    )
    parser.add_argument(
        "--review-config",
        type=str,
        help="审核专用配置文件路径"
    )

    # LLM options
    parser.add_argument(
        "--client",
        type=str,
        choices=["ollama", "openai_api"],
        help="LLM客户端类型"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="视觉模型名称"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API密钥 (用于openai_api客户端)"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        help="API URL (用于openai_api客户端)"
    )

    # Processing options
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="递归搜索子目录"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅检测不移动文件"
    )

    # Logging
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认: INFO)"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="日志文件路径"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)

    # Load configurations
    config = Config(args.config)

    # Override config with CLI arguments (使用默认硅基流动配置)
    if args.api_key:
        # 如果提供了API密钥，自动使用硅基流动配置
        config.config.setdefault('clients', {})['default'] = 'openai_api'
        config.config['clients'].setdefault('openai_api', {})['api_key'] = args.api_key
        config.config['clients']['openai_api']['api_url'] = args.api_url or DEFAULT_LLM_CONFIG['api_url']
    if args.client:
        config.config.setdefault('clients', {})['default'] = args.client
    if args.api_url:
        config.config.setdefault('clients', {}).setdefault('openai_api', {})['api_url'] = args.api_url

    review_config = load_review_config(args.review_config)

    # Create LLM client (only needed for rules 4-7)
    llm_client = None
    content_rules_needed = not args.rules or any(r in [4, 5, 6, 7] for r in args.rules)

    if content_rules_needed:
        llm_client = create_llm_client(config)
        if llm_client is None:
            logger.warning("LLM客户端未配置，规则4-7将被跳过")

    # Get model name (默认使用硅基流动的Qwen2-VL)
    model = args.model or DEFAULT_LLM_CONFIG['model']

    # Initialize reviewer
    reviewer = MVReviewer(
        config=review_config,
        llm_client=llm_client,
        model=model,
        enabled_rules=args.rules
    )

    # Process input
    input_path = Path(args.input)
    violation_dir = None if args.dry_run else Path(args.violation_dir)

    if input_path.is_file():
        # Single file review
        logger.info(f"审核单个文件: {input_path}")
        result = reviewer.review(input_path)

        if result.is_violation and violation_dir:
            reviewer._move_violation(input_path, violation_dir)

        results = [result]

    elif input_path.is_dir():
        # Batch review
        logger.info(f"批量审核目录: {input_path}")
        results = reviewer.review_batch(
            input_path,
            violation_dir=violation_dir,
            recursive=args.recursive
        )

    else:
        logger.error(f"输入路径不存在: {input_path}")
        sys.exit(1)

    # Generate and output report
    report = MVReviewer.generate_report(results)

    # Print summary
    summary = report['summary']
    logger.info("=" * 50)
    logger.info("审核完成!")
    logger.info(f"  总计: {summary['total']} 个视频")
    logger.info(f"  通过: {summary['passed']} 个")
    logger.info(f"  违规: {summary['violated']} 个")
    logger.info(f"  错误: {summary['errors']} 个")
    logger.info(f"  耗时: {summary['total_time_seconds']:.2f} 秒")

    if report['violations_by_rule']:
        logger.info("违规统计:")
        rule_names = {
            1: "作词作曲", 2: "竖屏/黑边", 3: "音量突变",
            4: "暴露/导向", 5: "纯风景", 6: "广告", 7: "吸毒"
        }
        for rule_id, count in sorted(report['violations_by_rule'].items()):
            logger.info(f"  规则{rule_id} ({rule_names.get(rule_id, '未知')}): {count} 个")

    # Save report to file
    if args.report:
        report_path = Path(args.report)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"报告已保存: {report_path}")

    # Exit with appropriate code
    if summary['violated'] > 0:
        sys.exit(1)  # Violations found
    elif summary['errors'] > 0:
        sys.exit(2)  # Errors occurred
    else:
        sys.exit(0)  # All passed


if __name__ == "__main__":
    main()
