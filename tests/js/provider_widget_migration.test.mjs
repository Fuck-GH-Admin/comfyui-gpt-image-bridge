import assert from "node:assert/strict";
import test from "node:test";

import {
    PROVIDER_WIDGET_COUNT,
    migrateLegacyWorkflowData,
    migrateProviderWidgetValues,
    resolvePasswordWidgetWidth,
} from "../../gpt_image_bridge/web/provider_widget_migration.js";

test("migrates the six-widget v0.4 layout into the grouped layout", () => {
    const migrated = migrateProviderWidgetValues([
        "key",
        "https://example.test/v1",
        "model",
        "auto",
        "images/generations",
        "images/edits",
    ]);
    assert.equal(migrated.length, PROVIDER_WIDGET_COUNT);
    assert.deepEqual(migrated.slice(4), [
        true,
        "images/generations",
        "images/edits",
        true,
        "",
        "",
        "",
        "",
    ]);
});

test("migrates the eight-widget v0.5 layout without swapping fields", () => {
    const migrated = migrateProviderWidgetValues([
        "key",
        "https://example.test/v1",
        "model",
        "images",
        false,
        true,
        "custom-generate",
        "custom-edit",
    ]);
    assert.equal(migrated.length, PROVIDER_WIDGET_COUNT);
    assert.deepEqual(migrated.slice(4), [
        false,
        "custom-generate",
        "custom-edit",
        true,
        "",
        "",
        "",
        "",
    ]);
});

test("keeps the current layout and unknown future layouts unchanged", () => {
    const defaultsOnly = ["key", "base", "model", "auto"];
    assert.equal(migrateProviderWidgetValues(defaultsOnly), defaultsOnly);
    const current = Array.from({ length: PROVIDER_WIDGET_COUNT }, (_, index) => index);
    assert.equal(migrateProviderWidgetValues(current), current);
    const future = Array.from({ length: PROVIDER_WIDGET_COUNT + 1 }, (_, index) => index);
    assert.equal(migrateProviderWidgetValues(future), future);
});

test("migrates a workflow copy without mutating its input", () => {
    const input = {
        id: 7,
        widgets_values: ["", "", "", "auto", "", ""],
    };
    const migrated = migrateLegacyWorkflowData(input);
    assert.notEqual(migrated, input);
    assert.equal(input.widgets_values.length, 6);
    assert.equal(migrated.widgets_values.length, PROVIDER_WIDGET_COUNT);
});

test("preserves the six-widget CLIProxyAPI provider on workflow reload", () => {
    const input = {
        type: "GPTImageBridgeCLIProxyAPIProvider",
        widgets_values: ["", "http://127.0.0.1:8317/v1", "gpt-image-2.6-flare", "", "images_edit", "auto"],
    };
    assert.equal(migrateLegacyWorkflowData(input), input);
    assert.deepEqual(input.widgets_values.slice(4), ["images_edit", "auto"]);
});

test("clamps a stale sidebar width only on the main graph canvas", () => {
    assert.equal(resolvePasswordWidgetWidth({
        drawingOnMainGraphCanvas: true,
        nodeWidth: 368,
        requestedWidth: 798,
    }), 368);
    assert.equal(resolvePasswordWidgetWidth({
        drawingOnMainGraphCanvas: false,
        nodeWidth: 368,
        requestedWidth: 798,
    }), 798);
    assert.equal(resolvePasswordWidgetWidth({
        drawingOnMainGraphCanvas: true,
        nodeWidth: 368,
        requestedWidth: Number.NaN,
    }), 368);
});
