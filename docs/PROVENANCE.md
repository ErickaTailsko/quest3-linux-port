# Origem e licenças

As revisões fixadas estão em `manifests/upstreams.json`.

| Referência | Uso |
|---|---|
| https://github.com/URFAVF3MBOY/quest2-steamos | referência do porte e primeiro alvo |
| https://github.com/YusufOzmen01/quest-kexec | loader e ferramentas de base |
| https://github.com/facebookincubator/oculus-linux-kernel | fonte pública do kernel |
| https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86 | toolchain fixada |
| https://github.com/Lumince/singularity | contexto do root e comportamento de boot |
| https://busybox.net/downloads/busybox-1.36.1.tar.bz2 | fonte BusyBox correspondente |
| https://android.googlesource.com/platform/system/logging/ | estudo logcat/logcatd Android14 |

O documento HOW_TO_PORT fornecido e as fontes originais recebidas estão nos
uploads. O guia não transforma endereços de Quest2/Pro em endereços seguros
para Quest3. As verificações foram feitas sobre DT/config/iomem específicos.

A licença GPLv2 da raiz cobre o código original deste projeto onde não houver
aviso específico. Fontes derivadas do kernel, pahole/dwarves e BusyBox preservam
seus avisos/licenças. A fonte BusyBox original e sua configuração são incluídas;
as licenças BusyBox e glibc também foram preservadas nos diretórios dos pacotes.
Fontes glibc correspondentes são distribuídas pelo Debian (glibc2.41-11), com
cross packages2.41-11cross1 registrados nos metadados; o script de rebuild
permite selecionar sysroot/cross compiler, inclusive libc modificada.

Arquivos AOSP mantêm seus avisos Apache2 quando aplicável. Bibliotecas e
binários fornecidos pelo usuário, diagnósticos, PDF e fontes de terceiros
mantêm seus direitos originais: a licença da raiz não os relicencia.
Não se atribui autoria do kernel, toolchain ou upstreams ao projeto Eris.

Dados brutos foram autorizados expressamente para este repositório público.
Credenciais de hospedagem/API, configurações de autenticação e dados internos
da sessão de ferramentas não fazem parte da publicação. Links de artefatos
externos são históricos e podem expirar; a release fornece uma cópia no GitHub.
