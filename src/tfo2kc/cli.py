# SPDX-FileCopyrightText: 2026-present Daniel Skowroński <tfo2kc@skowronski.cloud>
#
# SPDX-License-Identifier: BSD-3-Clause
import os
import sys
import json
import shutil
import subprocess
import click
from ruamel.yaml import YAML
import configparser

yaml = YAML()
yaml.default_flow_style = False

DEFAULT_KUBECONFIG = os.path.expanduser("~/.kube/config")
BACKUP_SUFFIX = ".bak"
DEFAULT_CONFIG_FILE = "tfo2kc.ini"

class ConfigError(Exception):
    pass

def fetch_tf_output(binary, key, cwd):
    """
    Call '<binary> output -json <key>' and return either the .value field or raw string.
    """
    proc = subprocess.run(
        [binary, "output", "-json", key],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    if isinstance(data, dict) and "value" in data:
        return data["value"]
    elif isinstance(data, str):
        return data
    else:
        raise ValueError(f"Unrecognized Terraform output format: {data!r}")

def upsert(entries, new_entry, key="name") -> bool:
    """
    Replace any existing entry with the same name, otherwise append.
    """
    for i, e in enumerate(entries):
        if e[key] == new_entry[key]:
            entries[i] = new_entry
            return True
    old_len = len(entries)
    entries.append(new_entry)
    new_len = len(entries)
    return new_len > old_len

@click.command()
@click.option('-t', '--terraform-binary', default=None,
              help='Terraform-compatible CLI (terraform, tofu, terragrunt).')
@click.option('-o', '--output-key', default=None,
              help='Terraform output key (dot-path) for the kubeconfig string.')
@click.option('-c', '--cluster-name', default=None,
              help='Name under which to store the cluster in kubeconfig.')
@click.option('-u', '--user-name', default=None,
              help='Username in kubeconfig (defaults to same as cluster name).')
@click.option('-x', '--context-name', default=None,
              help='Context name (defaults to <cluster>-ctx).')
@click.option('-k', '--kubeconfig', 'kubeconfig_path', default=None,
              help='Path to existing kubeconfig file (default ~/.kube/config).')
@click.option('-d', '--tf-dir', default=None,
              help='Directory where Terraform/terragrunt/tofu lives (default cwd).')
@click.option('-f', '--config-file', default=DEFAULT_CONFIG_FILE,
              help='INI file name or path in TF dir for defaults; default tfo2kc.ini.')
def main(terraform_binary, output_key, cluster_name, user_name,
         context_name, kubeconfig_path, tf_dir, config_file):
    """
    tfo2kc: Terraform/Terragrunt/openTofu Output 2 KubeConfig: CLI to merge kubeconfig obtained from TF output as string into ~/.kube/config
    """
    # Determine working directory and where to load the INI from
    tf_directory = tf_dir or os.getcwd()
    if os.path.isabs(config_file) or os.path.dirname(config_file):
        config_file_path = config_file
    else:
        config_file_path = os.path.join(tf_directory, config_file)

    # Load defaults from INI if present
    cfg = {}
    if os.path.exists(config_file_path):
        parser = configparser.ConfigParser()
        parser.read(config_file_path)
        if 'default' in parser:
            cfg = dict(parser['default'])

    # Resolve settings (CLI > INI > fixed defaults)
    terraform_bin = terraform_binary or cfg.get('terraform_binary', 'terraform')
    key_path      = output_key       or cfg.get('output_key')
    kube_path     = kubeconfig_path  or cfg.get('kubeconfig_path', DEFAULT_KUBECONFIG)
    cluster       = cluster_name     or cfg.get('cluster_name')
    user          = user_name        or cfg.get('user_name', cluster)
    ctx           = context_name     or cfg.get('context_name', f"{cluster}-ctx")

    # Ensure required values
    for name, val in (('output_key', key_path), ('cluster_name', cluster)):
        if not val:
            raise click.UsageError(f"Missing required setting: {name}")

    # Fetch the kubeconfig YAML string
    try:
        kube_str = fetch_tf_output(terraform_bin, key_path, tf_directory)
    except Exception as e:
        click.echo(f"Warning: failed to fetch Terraform output '{key_path}': {e}")
        sys.exit(1)

    # Load existing kubeconfig or initialize a blank one
    if os.path.exists(kube_path):
        existing_cfg = yaml.load(open(kube_path))
    else:
        existing_cfg = {
            'apiVersion': 'v1',
            'kind': 'Config',
            'preferences': {},
            'clusters': [],
            'users': [],
            'contexts': []
        }
    new_cfg = yaml.load(kube_str)

    # Backup before modifying
    shutil.copy2(kube_path, kube_path + BACKUP_SUFFIX)

    # Merge clusters/users/contexts and apply name overrides
    for cluster_entry in new_cfg.get('clusters', []):
        cluster_entry['name'] = cluster
        changed=upsert(existing_cfg['clusters'], cluster_entry)
        if changed:
            click.echo(f"Added/updated cluster '{cluster}' in kubeconfig.")
    for user_entry in new_cfg.get('users', []):
        user_entry['name'] = user
        changed=upsert(existing_cfg['users'], user_entry)
        if changed:
            click.echo(f"Added/updated user '{user}' in kubeconfig.")
    for ctx_entry in new_cfg.get('contexts', []):
        ctx_entry['name'] = ctx
        ctx_entry['cluster'] = cluster
        ctx_entry['user'] = user
        changed=upsert(existing_cfg['contexts'], ctx_entry)
        if changed:
            click.echo(f"Added/updated context '{ctx}' in kubeconfig.")

    # Preserve the original current-context
    if existing_cfg.get('current-context'):
        existing_cfg['current-context'] = existing_cfg['current-context']

    # Write out the merged kubeconfig
    with open(kube_path, 'w') as f:
        yaml.dump(existing_cfg, f)

if __name__ == '__main__':
    main()
  