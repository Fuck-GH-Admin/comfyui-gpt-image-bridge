/** Contextual widget presentation for GPT Image Bridge's canvas nodes.
 *
 * Never remove, reorder, rename, or disable serialization of an existing
 * request widget. Hidden widgets remain available to the backend and return
 * with their values intact when the corresponding mode is selected.
 *
 * Advanced parameter folding is ComfyUI native (showAdvanced / toggleAdvanced).
 */
export const PRESENTATION_NODE_TYPES = new Set([
    "GPTImageBridgeGenerate",
    "GPTImageBridgeEdit",
    "GPTImageBridgeProviderProfile",
]);
const LEGACY_ADVANCED_PROPERTY = "gpt_image_bridge_show_advanced";
const PREPARED_FLAG = "__gptImageBridgePresentationPrepared";
const CONDITIONED_FLAG = "__gptImageBridgeConditionedCallback";
const DEFAULTS = Object.freeze({
    moderation: "auto",
    timeout_sec: 300,
});
const ADVANCED_FIELDS = Object.freeze(["moderation", "timeout_sec"]);
const CUSTOM_SIZE_FIELDS = Object.freeze(["custom_width", "custom_height"]);
const FIELD_LABELS = Object.freeze({
    custom_width: "宽度 (px)",
    custom_height: "高度 (px)",
    timeout_sec: "超时 (秒)",
    moderation: "审核强度",
    responses_model: "Responses 主模型",
    image_model: "图像模型 (可覆盖)",
});

export function widgetByName(node, name) {
    return node?.widgets?.find((widget) => widget?.name === name);
}

function hasSocketLink(node, name) {
    return (node.inputs ?? []).some(
        (input) => input?.name === name
            && input.link !== null
            && input.link !== undefined,
    );
}

function hasNondefaultValue(widget, value) {
    return widget !== undefined && widget.value !== value;
}

export function desiredWidgetVisibility(node) {
    const type = node?.comfyClass || node?.type;
    if (!PRESENTATION_NODE_TYPES.has(type)) {
        return {};
    }

    if (type === "GPTImageBridgeProviderProfile") {
        const referenceMode = widgetByName(node, "reference_mode")?.value ?? "profile";
        const responseHost = widgetByName(node, "responses_model");
        return {
            // A text host is only relevant when reference generation selects
            // Responses; preserve nonempty overrides and connected sockets.
            responses_model: referenceMode === "responses"
                || hasSocketLink(node, "reference_mode")
                || hasNondefaultValue(responseHost, "")
                || hasSocketLink(node, "responses_model"),
        };
    }

    const visibility = {};
    const size = widgetByName(node, "size")?.value;
    const sizeDynamic = hasSocketLink(node, "size");
    const useCustom = size === "Custom" || sizeDynamic;
    for (const field of CUSTOM_SIZE_FIELDS) {
        // If size comes through a socket, it may change at execution time;
        // never hide the dimensions just because the current combo says auto.
        visibility[field] = useCustom || hasSocketLink(node, field);
    }
    return visibility;
}

function setHidden(widget, hidden) {
    if (!widget) {
        return false;
    }
    // ComfyUI_frontend 1.x and Nodes 2.0 both honor hidden/option.hidden.
    // Deliberately do not change widget.type/serialize/computeSize:
    // this must not break converted-to-input or positional workflow values.
    const changed = widget.hidden !== hidden || widget.options?.hidden !== hidden;
    if (!changed) {
        return false;
    }
    widget.options ??= {};
    widget.hidden = hidden;
    widget.options.hidden = hidden;
    return true;
}

function tagNativeAdvancedFields(node) {
    const type = node?.comfyClass || node?.type;
    if (type !== "GPTImageBridgeGenerate" && type !== "GPTImageBridgeEdit") {
        return false;
    }
    let changed = false;
    for (const field of ADVANCED_FIELDS) {
        const widget = widgetByName(node, field);
        if (!widget) continue;
        // ComfyUI owns advanced visibility, its context menu, and persistence.
        // Unusual values or connected inputs must remain readily visible.
        const advanced = (
            !hasNondefaultValue(widget, DEFAULTS[field])
            && !hasSocketLink(node, field)
        );
        if (widget.advanced === advanced && widget.options?.advanced === advanced) {
            continue;
        }
        widget.options ??= {};
        widget.advanced = advanced;
        widget.options.advanced = advanced;
        changed = true;
    }
    return changed;
}

function migrateLegacyAdvancedPreference(node) {
    const properties = node?.properties;
    if (!properties || !Object.prototype.hasOwnProperty.call(
        properties, LEGACY_ADVANCED_PROPERTY,
    )) return;
    if (properties[LEGACY_ADVANCED_PROPERTY] === true) {
        node.showAdvanced = true;
    }
    // Never resurrect the old per-node switch after a user hides advanced
    // options through ComfyUI's own control.
    delete properties[LEGACY_ADVANCED_PROPERTY];
}

function resizeKeepingWidth(node) {
    if (!Array.isArray(node?.size) || typeof node.computeSize !== "function") {
        return;
    }
    const width = node.size[0];
    const size = node.computeSize([...node.size]);
    if (!Array.isArray(size) || !Number.isFinite(size[1]) || size[1] <= 0) {
        return;
    }
    if (Math.abs(node.size[1] - size[1]) < 1) {
        return;
    }
    if (typeof node.setSize === "function") {
        node.setSize([width, size[1]]);
    } else {
        node.size[1] = size[1];
    }
}

function markDirty(node) {
    node.setDirtyCanvas?.(true, true);
    node.graph?.setDirtyCanvas?.(true, true);
}

export function applyContextualPresentation(node) {
    const visibility = desiredWidgetVisibility(node);
    let changed = false;
    for (const [field, shouldShow] of Object.entries(visibility)) {
        const widget = widgetByName(node, field);
        if (!widget) {
            continue;
        }
        changed = setHidden(widget, !shouldShow) || changed;
    }
    changed = tagNativeAdvancedFields(node) || changed;
    if (changed) {
        resizeKeepingWidth(node);
        markDirty(node);
    }
    return changed;
}

function wrapModeCallback(node, name) {
    const widget = widgetByName(node, name);
    if (!widget || widget[CONDITIONED_FLAG]) {
        return;
    }
    const original = widget.callback;
    widget.callback = function (...args) {
        const result = original?.apply(this, args);
        applyContextualPresentation(node);
        return result;
    };
    widget[CONDITIONED_FLAG] = true;
}

export function prepareContextualPresentation(node) {
    const type = node?.comfyClass || node?.type;
    if (!PRESENTATION_NODE_TYPES.has(type)) {
        return;
    }
    migrateLegacyAdvancedPreference(node);
    for (const [name, label] of Object.entries(FIELD_LABELS)) {
        const widget = widgetByName(node, name);
        if (widget) {
            widget.label = label;
        }
    }
    for (const name of ["size", "reference_mode", "moderation", "timeout_sec"]) {
        wrapModeCallback(node, name);
    }
    node[PREPARED_FLAG] = true;
    applyContextualPresentation(node);
}

export function isPresentationPrepared(node) {
    return node?.[PREPARED_FLAG] === true;
}
