import assert from "node:assert/strict";
import test from "node:test";
import {
    applyContextualPresentation,
    desiredWidgetVisibility,
    prepareContextualPresentation,
    widgetByName,
} from "../../gpt_image_bridge/web/node_presentation.js";

const base = {
    size: "auto", prompt: "A cinematic image",
    quality: "auto", background: "auto", output_format: "png",
    moderation: "auto", timeout_sec: 300, n: 1,
    custom_width: 1024, custom_height: 1024,
};

function fakeNode(type = "GPTImageBridgeGenerate", overrides = {}) {
    const values = type === "GPTImageBridgeProviderProfile" ? {
        profile: "local_codex", image_model: "",
        reference_mode: "profile", responses_model: "", ...overrides,
    } : { ...base, ...overrides };
    return {
        type, showAdvanced: false,
        properties: { existing: "keep" },
        widgets: Object.entries(values).map(([name, value]) => ({
            name, value, type: "combo", options: { serialize: true },
        })),
        inputs: [{ name: "provider", type: "GPT_IMAGE_PROVIDER", link: null }],
        size: [480, 760],
        computeSize() {
            return [320, 100 + 28 * this.widgets.filter(w => !w.hidden).length];
        },
        setSize(size) { this.size = size; this.resizeCalls = (this.resizeCalls ?? 0) + 1; },
        setDirtyCanvas() { this.dirtyCalls = (this.dirtyCalls ?? 0) + 1; },
    };
}

function change(node, name, value) {
    const widget = widgetByName(node, name);
    widget.value = value;
    widget.callback?.(value);
}

test("default Generate uses native advanced metadata, no Bridge toggle widget", () => {
    const node = fakeNode();
    const original = Object.fromEntries(node.widgets.map(w => [w.name, w.value]));
    prepareContextualPresentation(node);
    for (const key of ["prompt", "size", "quality", "background", "output_format", "n"]) {
        assert.notEqual(widgetByName(node, key).hidden, true);
    }
    for (const key of ["moderation", "timeout_sec"]) {
        const w = widgetByName(node, key);
        assert.equal(w.advanced, true);
        assert.equal(w.options.advanced, true);
        assert.equal(w.options.serialize, true);
        assert.notEqual(w.hidden, true);
    }
    for (const key of ["custom_width", "custom_height"]) {
        assert.equal(widgetByName(node, key).hidden, true);
    }
    assert.deepEqual(Object.fromEntries(node.widgets.map(w => [w.name, w.value])), original);
    assert.equal(node.widgets.length, Object.keys(original).length);
    assert.equal(node.properties.existing, "keep");
});

test("Edit image sockets stay unchanged; advanced behavior is native", () => {
    const node = fakeNode("GPTImageBridgeEdit");
    node.inputs.push({ name: "base_image（Image 1）", link: 4, type: "IMAGE" });
    node.inputs.push({ name: "mask", link: 7, type: "MASK" });
    const old = structuredClone(node.inputs);
    prepareContextualPresentation(node);
    assert.deepEqual(node.inputs, old);
    assert.equal(widgetByName(node, "moderation").advanced, true);
    assert.equal(widgetByName(node, "custom_width").hidden, true);
});

test("Custom shows dimensions and changing size preserves their values", () => {
    const node = fakeNode();
    prepareContextualPresentation(node);
    change(node, "size", "Custom");
    assert.equal(widgetByName(node, "custom_width").hidden, false);
    assert.equal(widgetByName(node, "custom_height").hidden, false);
    change(node, "custom_width", 2048);
    change(node, "custom_height", 1152);
    change(node, "size", "auto");
    assert.equal(widgetByName(node, "custom_width").hidden, true);
    assert.equal(widgetByName(node, "custom_width").value, 2048);
    change(node, "size", "Custom");
    assert.equal(widgetByName(node, "custom_height").value, 1152);
    assert.equal(widgetByName(node, "custom_width").hidden, false);
});

test("dynamic size socket keeps width and height visible", () => {
    const node = fakeNode();
    node.inputs.push({ name: "size", type: "STRING", link: 17 });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "custom_width").hidden, false);
    assert.equal(widgetByName(node, "custom_height").hidden, false);
    node.inputs.pop();
    applyContextualPresentation(node);
    assert.equal(widgetByName(node, "custom_width").hidden, true);
});

test("custom dimension socket remains available with preset size", () => {
    const node = fakeNode();
    node.inputs.push({ name: "custom_width", type: "INT", link: 10 });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "custom_width").hidden, false);
    assert.equal(widgetByName(node, "custom_height").hidden, true);
});

test("native ComfyUI showAdvanced persists without our own widget", () => {
    const node = fakeNode();
    const oldCount = node.widgets.length;
    prepareContextualPresentation(node);
    assert.equal(node.showAdvanced, false);
    node.showAdvanced = true;
    prepareContextualPresentation(node);
    assert.equal(node.showAdvanced, true);
    assert.equal(node.widgets.length, oldCount);
    assert.equal(widgetByName(node, "moderation").advanced, true);
    assert.equal(node.size[0], 480);
    assert.equal(node.widgets.some(w => w.name.includes("advanced_controls")), false);
});

test("legacy Bridge show advanced setting migrates once to native state", () => {
    const node = fakeNode();
    node.properties.gpt_image_bridge_show_advanced = true;
    prepareContextualPresentation(node);
    assert.equal(node.showAdvanced, true);
    assert.equal(node.properties.gpt_image_bridge_show_advanced, undefined);
    node.showAdvanced = false;
    prepareContextualPresentation(node);
    assert.equal(node.showAdvanced, false);
    assert.equal(node.properties.existing, "keep");
});

test("non-default moderation and timeout are not hidden behind advanced", () => {
    const node = fakeNode("GPTImageBridgeGenerate", {
        moderation: "low", timeout_sec: 900,
    });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "moderation").advanced, false);
    assert.equal(widgetByName(node, "timeout_sec").advanced, false);
    change(node, "moderation", "auto");
    change(node, "timeout_sec", 300);
    assert.equal(widgetByName(node, "moderation").advanced, true);
    assert.equal(widgetByName(node, "timeout_sec").advanced, true);
});

test("wired advanced control remains ordinary for inspection", () => {
    const node = fakeNode();
    node.inputs.push({ name: "moderation", type: "COMBO", link: 10 });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "moderation").advanced, false);
    assert.equal(widgetByName(node, "timeout_sec").advanced, true);
});

test("Profile shows Responses host only when useful or connected", () => {
    const node = fakeNode("GPTImageBridgeProviderProfile");
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "profile").hidden, undefined);
    assert.equal(widgetByName(node, "responses_model").hidden, true);
    change(node, "reference_mode", "responses");
    assert.equal(widgetByName(node, "responses_model").hidden, false);
    change(node, "responses_model", "text-host");
    change(node, "reference_mode", "images_edit");
    assert.equal(widgetByName(node, "responses_model").hidden, false);
    change(node, "responses_model", "");
    applyContextualPresentation(node);
    assert.equal(widgetByName(node, "responses_model").hidden, true);
});

test("Profile mode socket can resolve to Responses at execution time", () => {
    const node = fakeNode("GPTImageBridgeProviderProfile");
    node.inputs.push({ name: "reference_mode", link: 27, type: "COMBO" });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "responses_model").hidden, false);
    node.inputs.pop();
    applyContextualPresentation(node);
    assert.equal(widgetByName(node, "responses_model").hidden, true);
});

test("unknown node is untouched and repeated presentation is idempotent", () => {
    const node = fakeNode("UnknownNode");
    const widgets = structuredClone(node.widgets);
    prepareContextualPresentation(node);
    assert.deepEqual(node.widgets, widgets);
    assert.deepEqual(desiredWidgetVisibility(node), {});
    const target = fakeNode();
    prepareContextualPresentation(target);
    const count = target.widgets.length;
    const resizeCalls = target.resizeCalls;
    prepareContextualPresentation(target);
    assert.equal(target.widgets.length, count);
    assert.equal(target.resizeCalls, resizeCalls);
});
