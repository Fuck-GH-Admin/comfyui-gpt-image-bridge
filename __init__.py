if __package__:
    from .gpt_image_bridge.routes import register_routes
    from .nodes import (
        GPTImageBridgeEdit,
        GPTImageBridgeProviderProfile,
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
        GPTImageBridgeProviderProfile,
        GPTImageBridgeGenerate,
        GPTImageBridgeAPIProvider,
        GPTImageBridgeCLIProxyAPIProvider,
        GPTImageBridgeOAuthProvider,
        GPTImageBridgeReferenceList,
        GPTImageBridgeSaveImage,
    )

NODE_CLASS_MAPPINGS = {
    "GPTImageBridgeProviderProfile": GPTImageBridgeProviderProfile,
    "GPTImageBridgeAPIProvider": GPTImageBridgeAPIProvider,
    "GPTImageBridgeCLIProxyAPIProvider": GPTImageBridgeCLIProxyAPIProvider,
    "GPTImageBridgeOAuthProvider": GPTImageBridgeOAuthProvider,
    "GPTImageBridgeReferenceList": GPTImageBridgeReferenceList,
    "GPTImageBridgeGenerate": GPTImageBridgeGenerate,
    "GPTImageBridgeEdit": GPTImageBridgeEdit,
    "GPTImageBridgeSaveImage": GPTImageBridgeSaveImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GPTImageBridgeProviderProfile": "GPT Image Bridge · Provider Profile",
    "GPTImageBridgeAPIProvider": "GPT Image Bridge · API Provider",
    "GPTImageBridgeCLIProxyAPIProvider": "GPT Image Bridge · CLIProxyAPI Provider",
    "GPTImageBridgeOAuthProvider": "GPT Image Bridge · Codex OAuth Provider",
    "GPTImageBridgeReferenceList": (
        "GPT Image Bridge · Edit Reference List (Image 2–16)"
    ),
    "GPTImageBridgeGenerate": "GPT Image Bridge · Generate",
    "GPTImageBridgeEdit": "GPT Image Bridge · Edit",
    "GPTImageBridgeSaveImage": "GPT Image Bridge · Export JPEG/WebP (optional)",
}

WEB_DIRECTORY = "./gpt_image_bridge/web"
register_routes()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
