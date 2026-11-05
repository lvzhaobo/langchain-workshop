# 被 run.sh / check.sh source：把 "lab-01" / "01" / "lab-01-hello-graph" 解析成目录
resolve_lab() {
  local t="${1:-}" d b
  [ -z "$t" ] && return 1
  for d in labs/[0-9][0-9]-*; do
    [ -d "$d" ] || continue
    b=$(basename "$d")
    if [ "$b" = "$t" ] || [ "$b" = "lab-$t" ] || [ "${b#lab-}" = "$t" ]; then
      echo "$d"; return 0
    fi
  done
  # 前缀匹配：lab-01 → lab-01-hello-graph
  for d in labs/[0-9][0-9]-*; do
    [ -d "$d" ] || continue
    b=$(basename "$d")
    case "$b" in "lab-$t"-*|"$t"-*) echo "$d"; return 0;; esac
  done
  return 1
}
