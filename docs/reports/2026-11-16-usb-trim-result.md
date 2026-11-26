# Resultado USB trim1: build passou, redução insuficiente

**Image compilado com retorno zero e verificação de artefatos aprovada. Não
houve boot, envio de payload ou nova operação no Quest nesta etapa.**

## Tamanho e comparação

| Medida | QMP anterior | USB trim1 |
|---|---:|---:|
| Arquivo Image | 43.565.568 bytes | 39.418.368 bytes |
| image_size efetivo | 45.219.840 bytes | 41.025.536 bytes |
| image_size em MiB | 43,125 | 39,125 |

Redução efetiva: **4 MiB (9,2754%)**. Ainda faltariam 15,125 MiB de redução
para igualar o trecho MOVABLE histórico de 24 MiB, sem contar espaço de initrd/DT
se precisassem compartilhar esse mesmo trecho. Mesmo caber geometricamente não
demonstraria posse atual da RAM ou ausência de DMA.

Release: `5.10.246-gd7102a837402-q3-usb-trim1`.
SHA-256 Image: `c6c60da5cf958a7244c481ced5bd49b9a5bb2b29cb9770696939fa6695cc2fa5`.
SHA-256 config: `8cf9e3a6ebf7e7136ee706240168efc435254e1d148a3fb1a86e42abaf8dc29c`.

Seções de vmlinux medidas por llvm-size: text/readonly 27.555.331 bytes,
data 11.730.367, bss 1.563.088. Não substituir image_size pela soma dessas
classes nem pelo tamanho do arquivo Image.

## Checagens e limites

O verificador passou no perfil explícito usb-trim1, em modo image-only:
release/config, restrições do header, QMP embutido, flags CFI/SCS/LTO/x18,
símbolos e ELF64 ARM64. A tabela checada é vmlinux.symvers. **Não foi compilado
o conjunto completo de módulos nem validada ABI para módulos stock.**

O plano relativo conservador seria 40 MiB para Image + 2 MiB initrd + 2 MiB
DT, total 44 MiB. Nenhuma base foi escolhida; o loader/DT não foram alterados
para esse plano e ele não cabe nos trechos observados. O candidato anterior
permanece separado e não foi substituído como resultado de hardware validado.

O log contém aviso const de modpost e duas mensagens Git sobre a revisão
`dbc2bc83a~..HEAD`, indisponível no checkout raso. O processo make ainda chegou
a OBJCOPY Image e terminou com zero; essas mensagens não foram ocultadas.
O emissor exato da consulta Git não foi identificado nesta etapa, e não se
declara o build livre de diagnósticos ou plenamente reprodutível em binário.

Helpers net/ipv6 são compilados incondicionalmente ou por INET nesta árvore;
isso não significa que CONFIG_IPV6 tenha sido reativado. O hash da configuração
ativa foi conferido durante a compilação.

## Evidências preservadas

- `quest3/usb-trim/trim1-verification.json`;
- `quest3/usb-trim/trim1-geometry.json`;
- `quest3/usb-trim/trim1-comparison.json`;
- config e diff já publicados na pasta do projeto;
- cópia local do Image/config/mapas/log em
  `private-diagnostics/usb-trim1-artifacts/`, com manifesto de hashes;
- build completo Image-only em `.work/usb-trim1-final-config/`.

## Continuidade

Não tentar adaptar a janela ignorando os blocos UNMOVABLE. A próxima redução
deve revisar outros consumidores não necessários ao shell USB (por exemplo,
redes adicionais e filesystems em disco), mantendo provedores de plataforma e
proteções. A remoção de áudio exige resolver explicitamente a seleção do
framework DMA, não ativar um controlador de hardware arbitrário.

Não está demonstrado que cortes adicionais atinjam 24 MiB. Avaliar custos e
dependências antes de iniciar outro build. Posse, DMA, logs iniciais e handoff
CFI continuam bloqueios independentes do tamanho.
