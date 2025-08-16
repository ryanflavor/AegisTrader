#!/bin/bash
# enforce-uv.sh
# 强制使用uv的钩子

input=$(cat)

# Validate input
if [ -z "$input" ]; then
  echo '{"decision": "approve"}'
  exit 0
fi

# Extract fields with error handling
tool_name=$(echo "$input" | jq -r '.tool_name' 2>/dev/null || echo "")
command=$(echo "$input" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
file_path=$(echo "$input" | jq -r '.tool_input.file_path // .tool_input.path // ""' 2>/dev/null || echo "")
current_dir=$(pwd)

# ===== pip相关命令 =====
if [[ "$tool_name" == "Bash" ]]; then
  # 检查复合命令（包含 && 或 ; 的命令）
  if [[ "$command" =~ (&&|;) ]]; then
    # 分解命令并检查每个部分
    IFS=';&' read -ra PARTS <<< "$command"
    for part in "${PARTS[@]}"; do
      # 去除前后空格
      part=$(echo "$part" | xargs)
      # 检查是否包含需要拦截的命令
      if [[ "$part" =~ ^(pip|pip3|python|python3|py|pytest|mypy) ]]; then
        # 提取命令类型
        cmd_type=$(echo "$part" | grep -oE '^(pip|pip3|python|python3|py|pytest|mypy)' | head -1)
        echo "{
          \"decision\": \"block\",
          \"reason\": \"🔀 检测到复合命令中包含 $cmd_type\\n\\n原命令: $command\\n\\n建议将命令分开执行，并对 $cmd_type 使用 uv:\\n• cd 命令正常执行\\n• $cmd_type 命令改为 uv run $part\\n\\n示例:\\ncd /path && uv run $part\"
        }"
        exit 0
      fi

      # 检查是否包含 uv run pip 或 uv pip
      if [[ "$part" =~ ^uv\ (run\ )?pip\ install ]] || [[ "$part" =~ ^uv\ run\ python.*\ -m\ pip\ install ]]; then
        echo "{
          \"decision\": \"block\",
          \"reason\": \"🔀 检测到复合命令中包含 uv run pip install\\n\\n原命令: $command\\n\\n⚠️  'uv run pip install' 不会更新项目配置\\n\\n✅ 建议改为：\\n将命令分开执行，并使用 'uv add'：\\n• cd 命令正常执行\\n• pip install 改为 uv add\\n\\n示例：\\ncd /path && uv add <package>\"
        }"
        exit 0
      fi
    done
  fi

  case "$command" in
    uv\ pip\ *)
      # uv pip命令的处理
      uv_pip_cmd=$(echo "$command" | sed 's/^uv pip //' | xargs)

      case "$uv_pip_cmd" in
        install\ *)
          packages=$(echo "$uv_pip_cmd" | sed 's/install//' | sed 's/--[^ ]*//g' | xargs)

          # -r requirements.txt
          if [[ "$uv_pip_cmd" =~ -r\ .*\.txt ]]; then
            req_file=$(echo "$uv_pip_cmd" | sed -n 's/.*-r \([^ ]*\).*/\1/p')
            echo "{
              \"decision\": \"block\",
              \"reason\": \"⚠️  检测到 'uv pip install -r':\\n\\n❌ 不推荐: uv pip install -r $req_file\\n✅ 推荐: uv add -r $req_file\\n\\n为什么使用 'uv add'？\\n• 将依赖项保存到 pyproject.toml\\n• 自动生成/更新 uv.lock 文件\\n• 确保项目依赖的一致性\\n\\n💡 'uv pip' 只是临时安装，不会更新项目配置\"
            }"
            exit 0
          fi

          # 常规安装
          echo "{
            \"decision\": \"block\",
            \"reason\": \"⚠️  检测到 'uv pip install':\\n\\n❌ 不推荐: uv pip install $packages\\n✅ 推荐: uv add $packages\\n\\n为什么使用 'uv add'？\\n• 将依赖项保存到 pyproject.toml\\n• 自动生成/更新 uv.lock 文件\\n• 确保项目依赖的一致性\\n\\n💡 'uv pip' 只是临时安装，不会更新项目配置\"
          }"
          exit 0
          ;;

        *)
          # 其他uv pip命令
          echo "{
            \"decision\": \"block\",
            \"reason\": \"⚠️  'uv pip' 命令已弃用:\\n\\n请使用 uv 的包管理命令:\\n• 安装: uv add <package>\\n• 卸载: uv remove <package>\\n• 查看: uv tree\\n\\n💡 'uv pip' 不会更新项目配置文件\"
          }"
          exit 0
          ;;
      esac
      ;;

    pip\ *|pip3\ *)
      # pip命令的详细解析
      pip_cmd=$(echo "$command" | sed -E 's/^pip[0-9]? *//' | xargs)

      case "$pip_cmd" in
        install\ *)
          packages=$(echo "$pip_cmd" | sed 's/install//' | sed 's/--[^ ]*//g' | xargs)

          # -r requirements.txt
          if [[ "$pip_cmd" =~ -r\ .*\.txt ]]; then
            req_file=$(echo "$pip_cmd" | sed -n 's/.*-r \([^ ]*\).*/\1/p')
            echo "{
              \"decision\": \"block\",
              \"reason\": \"📋 从requirements.txt安装:\\n\\n✅ 推荐方法:\\nuv add -r $req_file\\n\\n这将会:\\n• 将requirements.txt中的所有依赖项添加到pyproject.toml\\n• 自动生成/更新uv.lock文件\\n• 自动同步虚拟环境\\n\\n💡 如果有约束文件:\\nuv add -r $req_file -c constraints.txt\\n\\n📌 注意: 这种方法最可靠，版本指定也会被正确处理\"
            }"
            exit 0
          fi

          # 开发依赖项
          if [[ "$pip_cmd" =~ --dev ]] || [[ "$pip_cmd" =~ -e ]]; then
            echo "{
              \"decision\": \"block\",
              \"reason\": \"🔧 安装开发依赖项:\\n\\nuv add --dev $packages\\n\\n可编辑安装: uv add -e .\"
            }"
            exit 0
          fi

          # 常规安装
          echo "{
            \"decision\": \"block\",
            \"reason\": \"📦 安装包:\\n\\nuv add $packages\\n\\n💾 'uv add' 会将依赖项保存到pyproject.toml\\n🔒 uv.lock保证可重现的环境\\n\\n💡 特殊情况:\\n• 从URL安装: 手动下载包后再添加\\n• 开发版: uv add --dev $packages\\n• 本地包: uv add -e ./path/to/package\"
          }"
          exit 0
          ;;

        uninstall\ *)
          packages=$(echo "$pip_cmd" | sed 's/uninstall//' | sed 's/-y//g' | xargs)
          echo "{
            \"decision\": \"block\",
            \"reason\": \"🗑️ 删除包:\\n\\nuv remove $packages\\n\\n✨ 依赖项也会自动清理\"
          }"
          exit 0
          ;;

        list*|freeze*)
          echo '{
            "decision": "block",
            "reason": "📊 查看包列表:\n\n• 项目依赖项: cat pyproject.toml\n• 锁文件详情: cat uv.lock\n• 已安装列表: uv tree\n• 导出为requirements.txt格式: uv export --format requirements-txt\n\n💡 'uv tree'会显示项目的依赖树"
          }'
          exit 0
          ;;

        *)
          # 其他pip命令（show, check等）
          echo "{
            \"decision\": \"block\",
            \"reason\": \"🔀 用uv执行pip命令:\\n\\nuv $pip_cmd\\n\\n💡 包的安装/删除请使用 'uv add/remove'\"
          }"
          exit 0
          ;;
      esac
      ;;

    # ===== mypy命令的处理 =====
    mypy\ *)
      # 提取mypy参数
      mypy_args=$(echo "$command" | sed 's/^mypy //')
      echo "{
        \"decision\": \"block\",
        \"reason\": \"🔍 使用uv运行mypy类型检查:\\n\\nuv run mypy $mypy_args\\n\\n✅ uv会自动使用项目的虚拟环境\\n💡 确保mypy已通过 'uv add --dev mypy' 安装\"
      }"
      exit 0
      ;;

    # ===== pytest命令的处理 =====
    pytest\ *)
      # 提取pytest参数
      pytest_args=$(echo "$command" | sed 's/^pytest //')
      echo "{
        \"decision\": \"block\",
        \"reason\": \"🧪 使用uv运行pytest测试:\\n\\nuv run pytest $pytest_args\\n\\n✅ uv会自动使用项目的虚拟环境\\n💡 确保pytest已通过 'uv add --dev pytest' 安装\"
      }"
      exit 0
      ;;

    # ===== 直接Python执行的处理 =====
    python*|python3*|py\ *)
      # 常规的uv转换
      args=$(echo "$command" | sed -E 's/^python[0-9]? //' | xargs)

      # -m 选项的特殊处理
      if [[ "$args" =~ ^-m ]]; then
        module=$(echo "$args" | sed 's/-m //')

        case "$module" in
          pip\ *)
            pip_cmd=$(echo "$module" | sed 's/pip //')
            # Parse pip install commands
            if [[ "$pip_cmd" =~ ^install ]]; then
              packages=$(echo "$pip_cmd" | sed 's/install//' | sed 's/--[^ ]*//g' | xargs)
              if [[ "$pip_cmd" =~ -r\ .*\.txt ]]; then
                req_file=$(echo "$pip_cmd" | sed -n 's/.*-r \([^ ]*\).*/\1/p')
                echo "{
                  \"decision\": \"block\",
                  \"reason\": \"📋 从requirements.txt安装:\\n\\n✅ 推荐方法:\\nuv add -r $req_file\\n\\n💡 这将把所有依赖项添加到pyproject.toml\"
                }"
              else
                echo "{
                  \"decision\": \"block\",
                  \"reason\": \"📦 安装包:\\n\\nuv add $packages\\n\\n💡 'uv add' 会将依赖项保存到pyproject.toml\"
                }"
              fi
            else
              echo "{
                \"decision\": \"block\",
                \"reason\": \"🔀 用uv执行pip命令:\\n\\nuv $pip_cmd\\n\\n💡 包管理请使用 'uv add/remove'\"
              }"
            fi
            exit 0
            ;;
          *)
            echo "{
              \"decision\": \"block\",
              \"reason\": \"用uv运行模块:\\n\\nuv run python -m $module\\n\\n🔄 uv会自动同步环境后再执行。\"
            }"
            exit 0
            ;;
        esac
      fi

      # 基本的Python执行
      echo "{
        \"decision\": \"block\",
        \"reason\": \"用uv执行Python:\\n\\nuv run python $args\\n\\n✅ 无需激活虚拟环境！\"
      }"
      exit 0
      ;;

    # ===== uv run pip 命令的处理 =====
    uv\ run\ pip\ *)
      # uv run pip命令的处理
      uv_run_pip_cmd=$(echo "$command" | sed 's/^uv run pip //' | xargs)

      case "$uv_run_pip_cmd" in
        install\ *)
          packages=$(echo "$uv_run_pip_cmd" | sed 's/install//' | sed 's/--[^ ]*//g' | xargs)

          # -r requirements.txt
          if [[ "$uv_run_pip_cmd" =~ -r\ .*\.txt ]]; then
            req_file=$(echo "$uv_run_pip_cmd" | sed -n 's/.*-r \([^ ]*\).*/\1/p')
            echo "{
              \"decision\": \"block\",
              \"reason\": \"⚠️  检测到 'uv run pip install -r':\\n\\n❌ 不推荐: uv run pip install -r $req_file\\n✅ 推荐: uv add -r $req_file\\n\\n为什么？\\n• 'uv run pip' 只在当前虚拟环境中安装\\n• 不会更新 pyproject.toml 和 uv.lock\\n• 其他开发者无法获得相同的依赖\\n\\n💡 使用 'uv add' 确保项目依赖的一致性\"
            }"
            exit 0
          fi

          # 常规安装
          echo "{
            \"decision\": \"block\",
            \"reason\": \"⚠️  检测到 'uv run pip install':\\n\\n❌ 不推荐: uv run pip install $packages\\n✅ 推荐: uv add $packages\\n\\n为什么？\\n• 'uv run pip' 只在当前虚拟环境中安装\\n• 不会更新 pyproject.toml 和 uv.lock\\n• 其他开发者无法获得相同的依赖\\n\\n💡 使用 'uv add' 确保项目依赖的一致性\"
          }"
          exit 0
          ;;

        *)
          # 其他uv run pip命令
          echo "{
            \"decision\": \"block\",
            \"reason\": \"⚠️  'uv run pip' 已弃用:\\n\\n请使用 uv 的包管理命令：\\n• 安装: uv add <package>\\n• 卸载: uv remove <package>\\n• 查看: uv tree\\n\\n💡 'uv run pip' 不会更新项目配置文件\"
          }"
          exit 0
          ;;
      esac
      ;;

    # ===== uv run python -m pip 命令的处理 =====
    uv\ run\ python*\ -m\ pip\ *)
      # 提取pip命令部分
      pip_cmd=$(echo "$command" | sed -E 's/^uv run python[0-9]* -m pip //' | xargs)

      case "$pip_cmd" in
        install\ *)
          packages=$(echo "$pip_cmd" | sed 's/install//' | sed 's/--[^ ]*//g' | xargs)

          # -r requirements.txt
          if [[ "$pip_cmd" =~ -r\ .*\.txt ]]; then
            req_file=$(echo "$pip_cmd" | sed -n 's/.*-r \([^ ]*\).*/\1/p')
            echo "{
              \"decision\": \"block\",
              \"reason\": \"⚠️  检测到 'uv run python -m pip install -r':\\n\\n❌ 不推荐: uv run python -m pip install -r $req_file\\n✅ 推荐: uv add -r $req_file\\n\\n为什么？\\n• 'uv run python -m pip' 只在当前虚拟环境中安装\\n• 不会更新 pyproject.toml 和 uv.lock\\n• 其他开发者无法获得相同的依赖\\n\\n💡 使用 'uv add' 确保项目依赖的一致性\"
            }"
            exit 0
          fi

          # 常规安装
          echo "{
            \"decision\": \"block\",
            \"reason\": \"⚠️  检测到 'uv run python -m pip install':\\n\\n❌ 不推荐: uv run python -m pip install $packages\\n✅ 推荐: uv add $packages\\n\\n为什么？\\n• 'uv run python -m pip' 只在当前虚拟环境中安装\\n• 不会更新 pyproject.toml 和 uv.lock\\n• 其他开发者无法获得相同的依赖\\n\\n💡 使用 'uv add' 确保项目依赖的一致性\"
          }"
          exit 0
          ;;

        *)
          # 其他pip命令
          echo "{
            \"decision\": \"block\",
            \"reason\": \"⚠️  'uv run python -m pip' 已弃用:\\n\\n请使用 uv 的包管理命令：\\n• 安装: uv add <package>\\n• 卸载: uv remove <package>\\n• 查看: uv tree\\n\\n💡 'uv run python -m pip' 不会更新项目配置文件\"
          }"
          exit 0
          ;;
      esac
      ;;
  esac
fi

# 默认批准
echo '{"decision": "approve"}'
