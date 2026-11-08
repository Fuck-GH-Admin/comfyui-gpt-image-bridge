import { app } from "../../scripts/app.js";
import {
    PRESENTATION_NODE_TYPES,
    applyContextualPresentation,
    prepareContextualPresentation,
} from "./node_presentation.js";

const SCHEDULED = "__gptImageBridgePresentationScheduled";

function schedulePresentation(node) {
    if (!node || node[SCHEDULED]) {
        return;
    }
    node[SCHEDULED] = true;
    setTimeout(() => {
        node[SCHEDULED] = false;
        prepareContextualPresentation(node);
    }, 0);
}

app.registerExtension({
    name: "GPTImageBridge.ContextualNodeControls",
    nodeCreated(node) {
        if (PRESENTATION_NODE_TYPES.has(node?.comfyClass || node?.type)) {
            schedulePresentation(node);
        }
    },
    loadedGraphNode(node) {
        if (PRESENTATION_NODE_TYPES.has(node?.comfyClass || node?.type)) {
            schedulePresentation(node);
        }
    },
    afterConfigureGraph() {
        for (const node of app.graph?._nodes ?? []) {
            if (PRESENTATION_NODE_TYPES.has(node?.comfyClass || node?.type)) {
                schedulePresentation(node);
            }
        }
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!PRESENTATION_NODE_TYPES.has(nodeData.name)) {
            return;
        }
        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = originalCreated?.apply(this, args);
            schedulePresentation(this);
            return result;
        };

        const originalConfigure = nodeType.prototype.configure;
        nodeType.prototype.configure = function (...args) {
            const result = originalConfigure?.apply(this, args);
            // Widget state and node properties are restored during configure.
            schedulePresentation(this);
            return result;
        };

        const originalOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (...args) {
            const result = originalOnConfigure?.apply(this, args);
            schedulePresentation(this);
            return result;
        };

        const originalOnWidgetChanged = nodeType.prototype.onWidgetChanged;
        nodeType.prototype.onWidgetChanged = function (name, ...args) {
            const result = originalOnWidgetChanged?.call(this, name, ...args);
            if (["size", "reference_mode", "moderation", "timeout_sec"].includes(name)) {
                applyContextualPresentation(this);
            }
            return result;
        };

        const originalConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function (...args) {
            const result = originalConnectionsChange?.apply(this, args);
            // A linked 'size' input can evaluate to Custom at queue time even
            // while the visible size widget itself still says auto.
            schedulePresentation(this);
            return result;
        };
    },
});
