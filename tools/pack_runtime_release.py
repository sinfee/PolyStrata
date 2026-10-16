"""把已验证的 Windows 主引擎与视觉编码器打成可校验发布包，不重新编译。"""
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import setup


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--vision', type=Path, required=True)
    parser.add_argument('--build-manifest', type=Path, required=True)
    parser.add_argument('--vision-manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    dirty = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'], text=True)
    if dirty.strip():
        raise RuntimeError('发布前必须提交源码，避免二进制无法对应源码提交')
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    build = json.loads(args.build_manifest.read_text(encoding='utf-8-sig'))
    vision = json.loads(args.vision_manifest.read_text(encoding='utf-8-sig'))
    if digest(args.engine).lower() != build['engineSha256'].lower():
        raise RuntimeError('主引擎与已验证构建清单不一致')
    if setup.source_hash(setup.ENGINE_SOURCES) != build['engineSourceHash']:
        raise RuntimeError('引擎源码在构建后发生变化，必须重新构建和验证')
    vision_src = setup.source_hash(setup.VISION_SOURCES)
    if vision_src != vision['vision_src']:
        raise RuntimeError('视觉编码器的源码指纹与当前仓库不一致')
    # 混合包按两个程序中较新的 CUDA 要求声明，避免误用旧动态库。
    cuda = max((build['cuda'], vision['cuda']), key=lambda v: tuple(map(int, v.split('.'))))
    metadata = {'source': 'release', 'version': setup.source_version(),
                'repository': 'sinfee/PolyStrata', 'source_commit': commit,
                'archs': [int(build['architecture'])], 'cuda': cuda,
                'src': setup.source_hash(setup.ENGINE_SOURCES), 'vision': 'gpu',
                'vision_src': vision_src, 'portable': False, 'build': build,
                'sha256': {'strata-poly.exe': digest(args.engine), 'strata-vision.exe': digest(args.vision)}}
    args.out.mkdir(parents=True, exist_ok=True)
    archive = args.out / setup.poly_asset()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as out:
        out.write(args.engine, 'strata-poly.exe')
        out.write(args.vision, 'strata-vision.exe')
        out.writestr('BUILD.json', json.dumps(metadata, ensure_ascii=False, indent=2))
    result = {'archive': str(archive), 'sha256': digest(archive), 'commit': commit, 'metadata': metadata}
    (args.out / 'release-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('archive', 'sha256', 'commit')}))


if __name__ == '__main__':
    main()
