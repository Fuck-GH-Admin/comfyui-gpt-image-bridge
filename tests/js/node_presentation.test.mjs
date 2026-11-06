import assert from "node:assert/strict";
import test from "node:test";

import {
    ADVANCED_PROPERTY,
    ADVANCED_WIDGET_NAME,
    applyContextualPresentation,
    desiredWidgetVisibility,
    prepareContextualPresentation,
    widgetByName,
} from "../../gpt_image_bridge/web/node_presentation.js";

const defaults = {
    size: "auto",
    quality: "auto",
    background: "auto",
    output_format: "png",
    moderation: "auto",
    timeout_sec: 300,
    n: 1,
    custom_width: 1024,
    custom_height: 1024,
};

function makeWidget(name, value) {
    return { name, value, type: "combo", options: { serialize: true } };
}

function fakeNode(type = "GPTImageBridgeGenerate", overrides = {}) {
    const values = type === "GPTImageBridgeProviderProfile"
        ? {
            profile: "local_codex",
            image_model: "",
            reference_mode: "profile",
            responses_model: "",
            ...overrides,
        }
        : { ...defaults, prompt: "A cinematic image", ...overrides };
    const node = {
        type,
        properties: { existing_user_property: "keep-me" },
        widgets: Object.entries(values).map(([name, value]) => makeWidget(name, value)),
        inputs: [
            { name: "provider", type: "GPT_IMAGE_PROVIDER", link: null },
            ...(type === "GPTImageBridgeEdit"
                ? [{ name: "base_image（Image 1）", type: "IMAGE", link: null }]
                : []),
        ],
        size: [480, 760],
        computeSize() {
            const shown = this.widgets.filter((widget) => !widget.hidden);
            return [300, 80 + 28 * shown.length + 15 * this.inputs.length];
        },
        setSize(newSize) {
            this.size = newSize;
            this.resizeCalls = (this.resizeCalls ?? 0) + 1;
        },
        addWidget(widgetType, name, value, callback, options) {
            const widget = { type: widgetType, name, value, callback, options };
            this.widgets.push(widget);
            return widget;
        },
        setDirtyCanvas() {
            this.dirtyCalls = (this.dirtyCalls ?? 0) + 1;
        },
    };
    return node;
}

function changed(node, field, value) {
    const widget = widgetByName(node, field);
    widget.value = value;
    widget.callback?.(value);
}

test("Generate: common controls stay visible, low-frequency controls collapse", () => {
    const node = fakeNode();
    const valuesBefore = Object.fromEntries(node.widgets.map(w => [w.name, w.value]));
    prepareContextualPresentation(node);
    for (const name of ["prompt", "size", "quality", "background", "output_format", "n"]) {
        assert.notEqual(widgetByName(node, name).hidden, true, name);
    }
    for (const name of ["moderation", "timeout_sec", "custom_width", "custom_height"]) {
        assert.equal(widgetByName(node, name).hidden, true, name);
        assert.equal(widgetByName(node, name).options.serialize, true, name);
    }
    assert.deepEqual(
        Object.fromEntries(node.widgets.filter(w => w.name !== ADVANCED_WIDGET_NAME).map(w => [w.name, w.value])),
        valuesBefore,
    );
    assert.equal(node.properties.existing_user_property, "keep-me");
});

test("Edit: basic controls and image/mask sockets are untouched", () => {
    const node = fakeNode("GPTImageBridgeEdit");
    node.inputs.push({ name: "mask", type: "MASK", link: 7 });
    const before = structuredClone(node.inputs);
    prepareContextualPresentation(node);
    assert.deepEqual(node.inputs, before);
    assert.equal(widgetByName(node, "moderation").hidden, true);
    assert.equal(widgetByName(node, "custom_width").hidden, true);
});

test("size=Custom reveals width/height; switching back hides only the controls", () => {
    const node = fakeNode();
    prepareContextualPresentation(node);
    changed(node, "size", "Custom");
    assert.equal(widgetByName(node, "custom_width").hidden, false);
    assert.equal(widgetByName(node, "custom_height").hidden, false);
    changed(node, "custom_width", 2048);
    changed(node, "custom_height", 1152);
    changed(node, "size", "auto");
    assert.equal(widgetByName(node, "custom_width").hidden, true);
    assert.equal(widgetByName(node, "custom_width").value, 2048);
    assert.equal(widgetByName(node, "custom_height").value, 1152);
    changed(node, "size", "Custom");
    assert.equal(widgetByName(node, "custom_width").value, 2048);
    assert.equal(widgetByName(node, "custom_height").hidden, false);
});

test("socket-driven size exposes both dimensions for dynamic Custom mode", () => {
    const node = fakeNode();
    node.inputs.push({ name: "size", type: "STRING", link: 17 });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "custom_width").hidden, false);
    assert.equal(widgetByName(node, "custom_height").hidden, false);
    node.inputs.pop();
    applyContextualPresentation(node);
    assert.equal(widgetByName(node, "custom_width").hidden, true);
});

test("connected custom dimension stays visible even if size is non-Custom", () => {
    const node = fakeNode();
    node.inputs.push({ name: "custom_width", type: "INT", link: 18 });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "custom_width").hidden, false);
    assert.equal(widgetByName(node, "custom_height").hidden, true);
});

test("advanced toggle is UI-only in prompt/workflow but its state persists via node.properties", () => {
    const node = fakeNode();
    prepareContextualPresentation(node);
    const toggle = widgetByName(node, ADVANCED_WIDGET_NAME);
    assert.equal(toggle.serialize, false);
    assert.equal(toggle.options.serialize, false);
    assert.equal(toggle.value, false);
    changed(node, ADVANCED_WIDGET_NAME, true);
    assert.equal(node.properties[ADVANCED_PROPERTY], true);
    assert.equal(widgetByName(node, "moderation").hidden, false);
    assert.equal(widgetByName(node, "timeout_sec").hidden, false);
    assert.equal(widgetByName(node, "custom_width").hidden, true);
    const size = [...node.size];
    assert.equal(size[0], 480, "Never overwrite the width chosen by the user");
    prepareContextualPresentation(node);
    assert.equal(node.widgets.filter(w => w.name === ADVANCED_WIDGET_NAME).length, 1);
    assert.equal(widgetByName(node, ADVANCED_WIDGET_NAME).value, true);
    changed(node, ADVANCED_WIDGET_NAME, false);
    assert.equal(widgetByName(node, "moderation").hidden, true);
});

test("non-default moderation or timeout is not silently buried when advanced is collapsed", () => {
    const node = fakeNode("GPTImageBridgeGenerate", {
        moderation: "low",
        timeout_sec: 900,
    });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "moderation").hidden, false);
    assert.equal(widgetByName(node, "timeout_sec").hidden, false);
    assert.equal(node.properties[ADVANCED_PROPERTY], false);
    changed(node, "moderation", "auto");
    changed(node, "timeout_sec", 300);
    applyContextualPresentation(node);
    assert.equal(widgetByName(node, "moderation").hidden, true);
    assert.equal(widgetByName(node, "timeout_sec").hidden, true);
});

test("incoming moderation socket prevents hiding its linked field", () => {
    const node = fakeNode();
    node.inputs.push({ name: "moderation", type: "COMBO", link: 10 });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "moderation").hidden, false);
    assert.equal(widgetByName(node, "timeout_sec").hidden, true);
});

test("Provider Profile reveals Responses host only when relevant or configured", () => {
    const node = fakeNode("GPTImageBridgeProviderProfile");
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "profile").hidden, undefined);
    assert.equal(widgetByName(node, "image_model").hidden, undefined);
    assert.equal(widgetByName(node, "reference_mode").hidden, undefined);
    assert.equal(widgetByName(node, "responses_model").hidden, true);
    assert.equal(widgetByName(node, ADVANCED_WIDGET_NAME), undefined);
    changed(node, "reference_mode", "responses");
    assert.equal(widgetByName(node, "responses_model").hidden, false);
    changed(node, "responses_model", "some-text-model");
    changed(node, "reference_mode", "images_edit");
    assert.equal(widgetByName(node, "responses_model").hidden, false);
    changed(node, "responses_model", "");
    applyContextualPresentation(node);
    assert.equal(widgetByName(node, "responses_model").hidden, true);
    assert.equal(node.properties.existing_user_property, "keep-me");
});

test("Provider Profile mode socket may resolve to Responses: keep main model visible", () => {
    const node = fakeNode("GPTImageBridgeProviderProfile");
    node.inputs.push({ name: "reference_mode", type: "COMBO", link: 27 });
    prepareContextualPresentation(node);
    assert.equal(widgetByName(node, "responses_model").hidden, false);
    node.inputs.pop();
    applyContextualPresentation(node);
    assert.equal(widgetByName(node, "responses_model").hidden, true);
});

test("unknown nodes are untouched and repeat calls do not leak new widgets", () => {
    const node = fakeNode("UnknownNode");
    const before = structuredClone(node.widgets);
    prepareContextualPresentation(node);
    assert.deepEqual(node.widgets, before);
    assert.deepEqual(desiredWidgetVisibility(node), {});
    const n2 = fakeNode();
    prepareContextualPresentation(n2);
    const count = n2.widgets.length;
    const resizeCalls = n2.resizeCalls;
    prepareContextualPresentation(n2);
    assert.equal(n2.widgets.length, count);
    assert.equal(n2.resizeCalls, resizeCalls);
});
