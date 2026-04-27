# tfo2kc: TerraForm Output 2 KubeConfig

A CLI tool which updates `~/.kube/config` with relevant cluster, user and context information sourced from single `kubeconfig` string extracted from *output* of Terraform-compatible tool (Terragrunt/OpenTofu). It is useful in scenarios where some TF provider bootstraps a Kubernetes cluster and initial admin `kubeconfig` file is retrievable as output. 

Some benefits:

- single command to prepare terminal to use fresh k8s cluster after TF finishes boostrap: `TF` -> `tfo2kc` -> `kubectl`
- no need to manage many paths in environmental variable `KUBECONFIG` - all config entries can be stored in single `~/.kube/config` so any tool can consume them 
- automatic rename of cluster, user and context objects, which tend to be all "default" when coming from many common k8s bootstrap tools; this is especially important when merging many kubeconfigs
- support for any source tool which behaves like `terraform output -json`
- automatic backup of `~/.kube/config`
- `tfo2kc.ini` config stored in TF directory for context dependent translation

## Installation

[![PyPI: tfo2kc](https://img.shields.io/pypi/v/tfo2kc?style=flat-square&label=PyPI%3A%20tfo2kc)](https://pypi.org/project/tfo2kc/)

```bash
pipx install tfo2kc
```

## Usage

### --help

```
Usage: tfo2kc [OPTIONS]

  tfo2kc: Terraform/Terragrunt/openTofu Output 2 KubeConfig: CLI to merge
  kubeconfig obtained from TF output as string into ~/.kube/config

Options:
  -t, --terraform-binary TEXT  Terraform-compatible CLI (terraform, tofu,
                               terragrunt).
  -o, --output-key TEXT        Terraform output key (dot-path) for the
                               kubeconfig string.
  -c, --cluster-name TEXT      Name under which to store the cluster in
                               kubeconfig.
  -u, --user-name TEXT         Username in kubeconfig (defaults to same as
                               cluster name).
  -x, --context-name TEXT      Context name (defaults to <cluster>-ctx).
  -k, --kubeconfig TEXT        Path to existing kubeconfig file (default
                               ~/.kube/config).
  -d, --tf-dir TEXT            Directory where Terraform/terragrunt/tofu lives
                               (default cwd).
  -f, --config-file TEXT       INI file name or path in TF dir for defaults;
                               default tfo2kc.ini.
  --help                       Show this message and exit.
```

### Direct invocation

```bash
tfo2kc -t terraform -o myKubeConfig -c my-cluster -d /path/to/terraform/dir
tfo2kc -t terragrunt -o myKubeConfig -c my-cluster -d /path/to/terraform/dir
tfo2kc -t /path/to/opentofu -o myKubeConfig -c my-cluster -d /path/to/terraform/dir
```

### Running in current directory

```bash
tfo2kc -o myKubeConfig -c my-cluster
```

### Running in another directory

```bash
tfo2kc -d /path/to/other/dir -o myKubeConfig -c other-cluster
```

### Using an INI file

Place a `tfo2kc.ini` file alongside your Terraform files:

```ini
[default]
terraform_binary = terraform
output_key       = myKubeConfig
cluster_name     = my-cluster
user_name        = my-user
context_name     = my-context
kubeconfig_path  = ~/.kube/config
```

Then run:

```bash
tfo2kc -d /path/to/terraform/dir
```

## Example usage in Terraform

[k0s_cluster](https://registry.terraform.io/providers/adnsio/k0s/latest/docs/resources/cluster):

```hcl
resource "k0s_cluster" "example" {
  # ... cluster setup ...
}

output "myKubeConfig" {
  value     = k0s_cluster.example.kubeconfig
  sensitive = true
}
```

tool invocation:

```bash
tfo2kc -d . -o myKubeConfig -c example-cluster
```
