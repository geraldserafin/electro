{ pkgs, config, ... }:

let
  root = config.devenv.root;
  notebook = "${root}/apps/notebook";
in
{
  packages = [ pkgs.uv ];

  languages.python = {
    enable = true;
    package = pkgs.python3.withPackages (p: [ p.sympy p.pytest ]);
  };

  # apps/notebook (React + Vite); `pnpm install` runs when entering the shell
  languages.javascript = {
    enable = true;
    directory = "."; # the pnpm workspace: apps/* and the TypeScript packages
    pnpm = {
      enable = true;
      install.enable = true;
    };
  };

  # the workspace packages importable from any directory (devenv's python module owns PYTHONPATH, so append)
  enterShell = ''
    export PYTHONPATH="${root}/packages/electro/src:${root}/packages/electro-schematic/src:${root}/packages/electro-render/src:${root}/packages/electro-notes/src:${root}/apps/notebook/python''${PYTHONPATH:+:$PYTHONPATH}"
  '';

  # `devenv up`: the notebook on http://localhost:5190, rebuilt from packages/ on every save
  processes = {
    python-bundle.exec = "node ${notebook}/scripts/bundle-python.mjs --watch";
    notebook.exec = "cd ${notebook} && pnpm exec vite --port 5190 --strictPort";
    # the notes server (Effect) on :5191, behind the notebook's /api; notes in .data/notes.sqlite
    notes-server.exec = "cd ${root}/apps/server && PORT=5191 DATABASE_PATH=${root}/.data/notes.sqlite pnpm dev";
  };
}
