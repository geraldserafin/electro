{ pkgs, config, ... }:

let
  root = config.devenv.root;
  notebook = "${root}/apps/notebook";
in
{
  packages = [ pkgs.uv ];

  languages.python = {
    enable = true;
    package = pkgs.python3.withPackages (p: [
      p.sympy
      p.pytest
    ]);
  };

  languages.javascript = {
    enable = true;
    directory = ".";
    pnpm = {
      enable = true;
      install.enable = true;
    };
  };

  enterShell = ''
    export PYTHONPATH="${root}/packages/electro/src:${root}/packages/electro-schematic/src:${root}/packages/electro-render/src:${root}/packages/electro-notes/src:${root}/apps/notebook/python''${PYTHONPATH:+:$PYTHONPATH}"
  '';

  services.postgres = {
    enable = true;
    listen_addresses = "127.0.0.1";
    port = 5192;
    initialDatabases = [
      {
        name = "electro";
        user = "postgres";
        pass = "postgres";
      }
    ];
  };

  dotenv.enable = true;

  processes = {
    python-bundle.exec = "node ${notebook}/scripts/bundle-python.mjs --watch";
    notebook.exec = "cd ${notebook} && pnpm exec vite --port 5190 --strictPort";
    notes-server = {
      exec = "cd ${root}/apps/server && PORT=5191 pnpm dev";
      after = [ "devenv:processes:postgres" ];
    };
  };
}
