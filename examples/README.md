# readwright examples

Each directory is a self-contained fake project with a `readme.yaml` (some also have a `README.md.j2`)
and the `README.md` that `readwright render` produces from them. Run `readwright render` inside one to
regenerate.

| Example | Shows |
| --- | --- |
| [kitchen-sink](kitchen-sink/) | Every general helper: logo/center header, badge presets + custom + donation badges with a global style, toc, screenshots with captions and dark/light variants, subdir gallery, `include_file`, `cli_help`, `snippet`, `details`, `callout`, `config_table`, `env_table`, `entry_points_table`, `columns`, `video`, `changelog`, `gh_link`, `related_repos`, `contributors`, `git_sha`/`git_tag`/`today`, `spdx_link`, an `unsplash()` hero image, a repo-local partial override |
| [config-only](config-only/) | No template at all: a fully annotated `readme.yaml` using every config key (including an Unsplash `banner:`), rendered by the packaged `base.md.j2`. Read it as the config reference |
| [rust-cli](rust-cli/) | `Cargo.toml` detection and the `cargo install` snippet; a custom `{shield: ...}` badge for crates.io, since there's no built-in preset |
| [go-cli](go-cli/) | `go.mod` detection and the `go install ...@latest` snippet |
| [dotnet-tool](dotnet-tool/) | `*.csproj` detection (`PackAsTool`) and the `dotnet tool install --global` snippet |
| [node-cli](node-cli/) | `package.json` detection, the `npm install` snippet and the `npm` badge preset |

The kitchen sink uses `git_sha()` and `today()`, so its committed `README.md` will always be a little
behind; that is deliberate, to show why those helpers are a poor fit for `readwright check`.
