#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
work=${Q3_WORK_ROOT:-"$repo/.work"}
mkdir -p "$work"
fetch_revision() {
    local target=$1 url=$2 revision=$3
    if [[ -e "$target" ]]; then
        local head
        if head=$(git -C "$target" rev-parse --verify HEAD 2>/dev/null); then
            [[ "$head" == "$revision" ]] || {
                echo "Árvore existente com outra revisão: $target" >&2; return 1;
            }
            return
        fi
        # Resume only an empty repository created by an interrupted fetch.
        [[ -d "$target/.git" && $(git -C "$target" remote get-url origin) == "$url" &&
           -z $(git -C "$target" status --porcelain --untracked-files=all) ]] || {
            echo "Diretório incompleto/desconhecido; preservado: $target" >&2; return 1;
        }
    else
        git init "$target"
        git -C "$target" remote add origin "$url"
    fi
    git -C "$target" fetch --depth=1 origin "$revision"
    git -C "$target" checkout --detach FETCH_HEAD
}
fetch_revision "$work/kernel" https://github.com/facebookincubator/oculus-linux-kernel.git dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f
fetch_revision "$work/clang-prebuilts" https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86 425c8149f17c8d9914bf690b4d5abe45a13fb993
echo 'Fontes preparadas; nenhum comando de aparelho executado.'
