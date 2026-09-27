{ pkgs, config, ... }:

{
  packages = [ pkgs.uv ];

  languages.python = {
    enable = true;
    package = pkgs.python3.withPackages (p: [ p.sympy p.pytest ]);
  };

  # apps/notebook (React + Vite)
  languages.javascript = {
    enable = true;
    pnpm.enable = true;
  };

  env.PYTHONPATH = "${config.devenv.root}/packages/electro/src:${config.devenv.root}/packages/electro-schematic/src:${config.devenv.root}/packages/electro-render/src:${config.devenv.root}/apps/notebook/python";
}
