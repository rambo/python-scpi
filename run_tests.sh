#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
engine=${CONTAINER_ENGINE:-docker}
case "$engine" in
    docker|podman) ;;
    *) echo 'CONTAINER_ENGINE must be docker or podman' >&2; exit 1 ;;
esac
build_args=(--add-host=host.docker.internal:host-gateway)
if [ -n "${WHEELHOUSE_URL:-}" ]; then
    build_args+=(--build-arg "UV_FIND_LINKS=$WHEELHOUSE_URL")
fi
if [ "$engine" = podman ]; then
    build_args+=(--format docker)
fi
# Containers use copies of the source, so host virtualenvs and SSH sockets are not mounted.
for variant in ${VARIANTS:-debian alpine}; do
    case "$variant" in
        debian) dockerfile=Dockerfile ;;
        alpine) dockerfile=Dockerfile_alpine ;;
        *) echo "Unknown variant: $variant" >&2; exit 1 ;;
    esac
    for target in ${TARGETS:-test tox devel_shell production}; do
        tag="scpi-check:${target}-${variant}"
        "$engine" build "${build_args[@]}" --file "$dockerfile" --target "$target" --tag "$tag" .
        case "$target" in
            test|tox) "$engine" run --rm "$tag" ;;
            devel_shell) "$engine" run --rm "$tag" -c 'uv run --locked python -c "import scpi; print(scpi.__version__)"' ;;
            production)
                "$engine" run --rm "$tag"
                "$engine" run --rm "$tag" python -c 'from scpi.devices.hp6632b import HP6632B; from scpi.wrapper import AIOWrapper'
                ;;
            *) echo "Unknown target: $target" >&2; exit 1 ;;
        esac
    done
done
