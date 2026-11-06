from __future__ import annotations

from dataclasses import replace
from email.parser import BytesParser
import json

import pytest

from conftest import FakeResponse, QueueOpener, image_tensor
from gpt_image_bridge.images import tensor_to_png
from gpt_image_bridge.protocols import execute_operation
from gpt_image_bridge.transport import HttpClient


@pytest.mark.parametrize('operation,reference_guided', [('generate', False), ('edit', False), ('generate', True)])
@pytest.mark.parametrize('moderation', ['auto', 'low'])
@pytest.mark.parametrize('quality,output_format,background', [
    ('auto', 'png', 'auto'),
    ('low', 'jpeg', 'opaque'),
    ('medium', 'webp', 'transparent'),
    ('high', 'png', 'opaque'),
    ('xhigh', 'webp', 'opaque'),
    ('max', 'png', 'opaque'),
])
def test_images_transport_keeps_selected_controls(cliproxy_provider, image_json, operation, reference_guided, moderation, quality, output_format, background):
    provider = replace(cliproxy_provider, reference_generate_mode='images_edit', image_complexity='medium')
    image = tensor_to_png(image_tensor(15, 17), role='base')
    opener = QueueOpener(FakeResponse(image_json))
    execute_operation(
        provider=provider,
        operation=operation,
        prompt='a flat geometric icon',
        base_image=image if operation == 'edit' else None,
        references=(image,) if reference_guided else (),
        size='1024x768',
        quality=quality,
        background=background,
        output_format=output_format,
        moderation=moderation,
        client=HttpClient(opener=opener),
    )
    request = opener.requests[0][0]
    if request.get_header('Content-type').startswith('application/json'):
        fields = json.loads(request.data)
    else:
        mime = ('Content-Type: ' + request.get_header('Content-type') + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + request.data
        message = BytesParser().parsebytes(mime)
        fields = {part.get_param('name', header='content-disposition'): part.get_payload(decode=True).decode() for part in message.get_payload() if not part.get_filename()}
    assert fields['model'] == provider.model
    assert fields['size'] == '1024x768'
    assert fields['quality'] == quality
    assert fields['complexity'] == 'medium'
    assert fields['background'] == background
    assert fields['output_format'] == output_format
    assert fields['moderation'] == moderation
    assert str(fields['n']) == '1'


@pytest.mark.parametrize('n', [1, 2, 8])
def test_cliproxy_count_produces_one_request_per_output(cliproxy_provider, image_json, n):
    provider = replace(cliproxy_provider, reference_generate_mode='images_edit')
    opener = QueueOpener(*(FakeResponse(image_json) for _ in range(n)))
    result = execute_operation(provider=provider, operation='generate', prompt='an icon', n=n, client=HttpClient(opener=opener))
    assert len(result.images) == n
    assert len(opener.requests) == n
    assert all(json.loads(request.data)['n'] == 1 for request, _ in opener.requests)


@pytest.mark.parametrize('n', [0, 9])
def test_invalid_count_never_dispatches_a_request(cliproxy_provider, n):
    opener = QueueOpener()
    with pytest.raises(ValueError, match='between 1 and 8'):
        execute_operation(provider=cliproxy_provider, operation='generate', prompt='an icon', n=n, client=HttpClient(opener=opener))
    assert not opener.requests
