# SPDX-License-Identifier: MIT
#!/usr/bin/env python3
"""Extract full-size sprite-video frames using actual PTS or display indices.

Requires ffmpeg and ffprobe on PATH; no Python packages or network calls.
Output is an inspection artifact, not a normalized or pixel-repaired sprite.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Command failed: ' + command[0])
    return result.stdout


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def extract(video, out, times=None, indices=None):
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        raise ValueError('ffmpeg and ffprobe must be available on PATH')
    video = video.expanduser().resolve()
    out = out.expanduser().resolve()
    if not video.is_file():
        raise ValueError('Video file does not exist: ' + str(video))
    if out.exists() and any(out.iterdir()):
        raise ValueError('Use an empty or new output directory; previous outputs are preserved')

    media_command = [ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)]
    media = json.loads(run(media_command))
    stream = next((s for s in media.get('streams', []) if s.get('codec_type') == 'video'), None)
    if stream is None:
        raise ValueError('Input has no video stream')
    size = (int(stream['width']), int(stream['height']))
    pts_command = [ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_frames',
                   '-show_entries', 'frame=best_effort_timestamp_time,pts_time,coded_picture_number',
                   '-of', 'json', str(video)]
    probe_frames = json.loads(run(pts_command)).get('frames', [])
    frame_pts = []
    for index, frame in enumerate(probe_frames):
        text = frame.get('best_effort_timestamp_time', frame.get('pts_time'))
        if text is None or not math.isfinite(float(text)):
            raise ValueError('Frame %d has no usable actual PTS' % index)
        frame_pts.append({'source_index': index, 'pts': float(text), 'pts_text': text,
                          'coded_picture_number': frame.get('coded_picture_number')})
    if not frame_pts:
        raise ValueError('Input has no decodable video frames')

    requested = []
    if times is not None:
        first, last = frame_pts[0]['pts'], frame_pts[-1]['pts']
        for target in times:
            if not math.isfinite(target) or not first <= target <= last:
                raise ValueError('Requested time %s is outside actual frame PTS [%s, %s]' % (target, first, last))
            index = min(range(len(frame_pts)), key=lambda i: abs(frame_pts[i]['pts'] - target))
            requested.append({'requested_time': target, 'source_index': index})
    else:
        for index in indices:
            if not 0 <= index < len(frame_pts):
                raise ValueError('Source index %d is outside [0, %d]' % (index, len(frame_pts) - 1))
            requested.append({'requested_index': index, 'source_index': index})

    unique_indices = sorted({r['source_index'] for r in requested})
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / 'media.json', {
        'video': video.name, 'width': size[0], 'height': size[1],
        'codec': stream.get('codec_name'), 'duration': stream.get('duration')})
    write_json(out / 'frame_pts.json', {'frame_numbering': 'zero-based decoded display order', 'frames': frame_pts})
    expression = '+'.join('eq(n\\,%d)' % index for index in unique_indices)
    command = [ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(video),
               '-map', '0:v:0', '-vf', 'select=' + expression, '-vsync', '0',
               '-c:v', 'png', '-pix_fmt', 'rgba', '-start_number', '0', str(out / 'selected_%06d.png')]
    run(command)
    paths = {}
    for output_index, source_index in enumerate(unique_indices):
        temporary = out / ('selected_%06d.png' % output_index)
        if not temporary.is_file():
            raise ValueError('Missing decoded frame: %d' % source_index)
        with temporary.open('rb') as file:
            header = file.read(24)
        if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', header[16:24]) != size:
            raise ValueError('Extracted PNG does not retain source dimensions')
        destination = out / ('frame_%06d.png' % source_index)
        temporary.replace(destination)
        paths[source_index] = destination.name
    for record in requested:
        actual = frame_pts[record['source_index']]
        record.update({'actual_pts': actual['pts'], 'actual_pts_text': actual['pts_text'],
                       'path': paths[record['source_index']]})
        if 'requested_time' in record:
            record['time_error_seconds'] = round(actual['pts'] - record['requested_time'], 9)
    digest = hashlib.sha256()
    with video.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    manifest = {'source_video': video.name, 'source_sha256': digest.hexdigest(),
                'source_size': list(size), 'decoded_frame_count': len(frame_pts),
                'request_mode': 'time' if times is not None else 'index',
                'unique_extracted_frames': len(unique_indices), 'selections': requested,

                'processing': 'Decode/select only; no crop, resize, keying or frame interpolation'}
    write_json(out / 'selection.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--times', nargs='+', type=float)
    selection.add_argument('--indices', nargs='+', type=int)
    args = parser.parse_args()
    try:
        result = extract(args.video, args.out, args.times, args.indices)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, 'Extraction failed: ' + str(error) + '\n')
    print(json.dumps({'output': str(args.out.resolve()), 'source_size': result['source_size'],
                      'unique_extracted_frames': result['unique_extracted_frames'],
                      'selections': result['selections']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
