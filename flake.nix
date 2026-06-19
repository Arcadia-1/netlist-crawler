{
  description = "Development shell for netlist-crawler";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python313;
          pythonPackages = pkgs.python313Packages;
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pythonPackages.click
              pythonPackages.coverage
              pythonPackages.hatchling
              pythonPackages.numpy
              pythonPackages.pytest
              pythonPackages.scipy
            ];

            shellHook = ''
              export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
              echo "netlist-crawler dev shell"
              echo "Run: python -m pytest -q"
            '';
          };
        });
    };
}
