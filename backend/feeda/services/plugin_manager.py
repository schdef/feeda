import os
import asyncio
import inspect
import importlib.util
import logging

logger = logging.getLogger(__name__)

class HookManager:
    def __init__(self):
        self.hooks = {
            'before_feed_fetch': [],
            'after_feed_parse': [],
            'process_article': [],
            'score_article': [],
            'on_user_action': [],
        }

    def register(self, hook_name: str, callback: callable):
        if hook_name in self.hooks:
            self.hooks[hook_name].append(callback)

    async def run(self, hook_name: str, *args, **kwargs):
        if hook_name in self.hooks:
            for callback in self.hooks[hook_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Plugin error in hook {hook_name}: {e}")

hook_manager = HookManager()

def discover_plugins(plugins_dir: str):
    if not os.path.exists(plugins_dir):
        return
        
    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            path = os.path.join(plugins_dir, filename)
            spec = importlib.util.spec_from_file_location(filename[:-3], path)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                if hasattr(mod, 'register'):
                    mod.register(hook_manager)
                    logger.info(f"Loaded plugin: {filename}")
            except Exception as e:
                logger.error(f"Error loading plugin {filename}: {e}")
