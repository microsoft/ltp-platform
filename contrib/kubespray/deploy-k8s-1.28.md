Deploy kubernetes 1.28 with kubespray and pai scritps:

```bash
bash quick-start-kubespray.sh
```

on master machine, run `cp /etc/kubernetes/admin.conf ~/.kube/`.
Make sure `KUBECONFIG` environment variable is set to point to the path of your kubeconfig file.

Tested OS:
- WSL, Ubuntu 22.04
