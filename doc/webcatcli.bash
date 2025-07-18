#!/usr/bin/env bash
# Bash completion for webcatcli

_webcatcli() {
    local cur opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    opts="--max-line-length --no-javadoc --no-author --no-version \
--allow-globals --allow-empty --allow-unused --no-annotations \
--no-delta --no-method-cov --no-branch-cov --enable-cli-report \
--no-override --run-tests --run-main --external-jar \
--no-package-annotation --no-package-javadoc --debug --version \
--no-cleanup"
    if [[ "${cur}" == -* ]]; then
        COMPREPLY=( $(compgen -W "${opts}" -- "${cur}") )
    fi
    return 0
}
complete -F _webcatcli webcatcli

