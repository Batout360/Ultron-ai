"""Quick verification test for ULTRON core imports and LLM connectivity."""
import sys, asyncio
sys.path.insert(0, '.')

def test_settings():
    from config.settings import load_settings
    cfg = load_settings()
    print(f"Settings loaded:")
    print(f"  Model: {cfg.llm.model}")
    print(f"  Endpoint: {cfg.llm.endpoint}")
    print(f"  STT device (auto-detected): {cfg.stt.device}")
    print(f"  DB path: {cfg.db_path}")
    return cfg

async def test_llm(cfg):
    from ai.llm_provider import create_llm_provider
    llm = create_llm_provider(cfg)
    connected = await llm.check_connection()
    status = "CONNECTED" if connected else "FAILED"
    print(f"\nOllama connection: {status}")
    if connected:
        result = await llm.complete([{"role": "user", "content": "Say hello in exactly 5 words."}])
        print(f"LLM response: {result.content[:100]}")
    await llm.close()
    return connected

def test_imports():
    modules = [
        "core.event_bus", "core.state", "core.conversation",
        "core.memory", "core.assistant",
        "ai.llm_provider", "ai.streaming", "ai.prompts",
        "security.permissions", "security.confirmations",
        "storage.database", "storage.memory_store",
        "tools.registry", "tools.system", "tools.browser",
        "tools.files", "tools.applications",
        "ui.animations", "ui.app", "ui.main_window",
        "ui.components.chat_widget", "ui.components.panels",
    ]
    print("\nModule import test:")
    ok = 0
    for m in modules:
        try:
            __import__(m)
            print(f"  OK  {m}")
            ok += 1
        except Exception as e:
            print(f"  ERR {m}: {e}")
    print(f"\n{ok}/{len(modules)} modules imported successfully.")
    return ok == len(modules)

if __name__ == "__main__":
    cfg = test_settings()
    all_ok = test_imports()
    asyncio.run(test_llm(cfg))
    sys.exit(0 if all_ok else 1)
