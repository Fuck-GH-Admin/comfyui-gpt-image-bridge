if __package__:
    from .gpt_image_bridge.routes import register_routes
    from .nodes import (
        GPTImageBridgeEdit,
        GPTImageBridgeGenerate,
        GPTImageBridgeAPIProvider,
        GPTImageBridgeCLIProxyAPIProvider,
        GPTImageBridgeOAuthProvider,
        GPTImageBridgeReferenceList,
        GPTImageBridgeSaveImage,
    )
else:
    from gpt_image_bridge.routes import register_routes
    from nodes import (
        GPTImageBridgeEdit,
        GPTImageBridgeGenerate,
        GPTImageBridgeAPIProvider,
        GPTImageBridgeCLIProxyAPIProvider,
        GPTImageBridgeOAuthProvider,
        GPTImageBridgeReferenceList,
    )

NODE_CLASS_MAPPINGS = {
    "GPTImageBridgeAPIProvider": GPTImageBridgeAPIProvider,
    "GPTImageBridgeCLIProxyAPIProvider": GPTImageBridgeCLIProxyAPIProvider,
    "GPTImageBridgeOAuthProvider": GPTImageBridgeOAuthProvider,
    "GPTImageBridgeReferenceList": GPTImageBridgeReferenceList,
    "GPTImageBridgeGenerate": GPTImageBridgeGenerate,
    "GPTImageBridgeEdit": GPTImageBridgeEdit,
    "GPTImageBridgeSaveImage": GPTImageBridgeSaveImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GPTImageBridgeAPIProvider": "GPT Image Bridge · API Provider",
    "GPTImageBridgeCLIProxyAPIProvider": "GPT Image Bridge · CLIProxyAPI Provider",
    "GPTImageBridgeOAuthProvider": "GPT Image Bridge · Codex OAuth Provider",
    "GPTImageBridgeReferenceList": (
        "GPT Image Bridge · Edit Reference List (Image 2–16)"
    ),
    "GPTImageBridgeGenerate": "GPT Image Bridge · Generate",
    "GPTImageBridgeEdit": "GPT Image Bridge · Edit",
    "GPTImageBridgeSaveImage": "GPT Image Bridge · Save Image",
}

WEB_DIRECTORY = "./gpt_image_bridge/web"
register_routes()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
