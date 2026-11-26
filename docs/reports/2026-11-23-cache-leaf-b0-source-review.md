# B0 — caller e descoberta de linha (revisão textual)

Offline, sem candidato, preprocessamento, compilação, link, Kbuild/dry-run ou
operação no Quest. **B0 permanece PENDING.** Continuação do
[plano isolado](2026-11-19-cache-leaf-isolated-build-plan.md).

## Geometria: interfaces diferentes

`arch/arm64/kernel/cacheinfo.c:20–27` implementa/exporta GPL `cache_line_size`.
Symvers fornecido: `0x605d5bfa`, `vmlinux`, sem namespace. Retorna
`coherency_max_size` quando disponível: o **máximo** registrado em
`drivers/base/cacheinfo.c:256–258`. O fallback em `asm/cache.h:87–99` usa CWG,
ou `ARCH_DMA_MINALIGN` (128), não DminLine.

Não usar esse máximo como passo automático de manutenção: um passo maior pode
omitir linhas intermediárias menores. Alinhamento DMA não prova granularidade.
`asm/assembler.h:289–329` distingue CTR raw local do valor sistêmico seguro.
O caminho de alternatives pode referenciar `arm64_ftr_reg_ctrel0`, ausente dos
exports fornecidos; não resolver esse dado por endereço privado.

Existe alternativa pública promissora: `read_sanitised_ftr_reg(u32 id)`,
declarada em `asm/cpufeature.h:608`, implementada/exportada em
`arch/arm64/kernel/cpufeature.c:1234–1242`. Symvers fornecido:
`0x3562f983`, `vmlinux`, `EXPORT_SYMBOL_GPL`, sem namespace.
`ftr_ctr` classifica DminLine como `FTR_LOWER_SAFE` (380), diferentemente de
CWG. O kernel extrai DminLine de CTR sanitizado em `alternative.c:118–133`.

Isso fundamenta uma hipótese de consulta pública **no caller**, não uma
implementação aprovada. A função retorna zero para ID desconhecido: não converter
esse fallback silenciosamente em geometria validada. Revisar ID, inicialização,
domínio, CPUs/hotplug, momento da leitura e validade até o uso. Não consultar
geometria no init de recusa. Se for preciso alterar ABI, revisar contrato e
verificador antes; não mudar assinatura implicitamente para obter PASS.

O precedente de `alternative.c` é privado e usa `dc civac` por erratas A53.
Não copiar função, `__nocfi`, operação ou barreiras por analogia. Geometria
sanitizada não prova erratas, mappings, ownership, DMA, última escrita ou PoC.

## Retenção Full LTO

`include/linux/compiler_attributes.h` define:

- `noinline` (239): não demonstra retenção de código morto.
- `__used` (305): proposta de emissão a revisar, não prova de sobrevivência
  do caller e call ao pipeline inteiro/LTO/link.
- `__visible` (159–168): opcional, documentado como não suportado por Clang;
  não depender dele para reter caller nesta toolchain.
- `__maybe_unused` (299): não substitui retenção.

Proposta documental: caller C conhecido, `__used`/`noinline` sujeitos a revisão
e confirmação no ELF futuro, sem callback ou ponteiro armazenado. Não foi
testado o comportamento desses atributos com Clang 14 local. Não usar export,
chamada no init ou desativação de CFI/Full LTO para forçar presença.
`__used` não permite ignorar escapes reais; distinguir metadata do compilador
de referência de dados operacional.

O artefato futuro precisa conter caller identificado, chamada direta real,
ABI compatível e retornos protegidos. Tail-call, clones, veneers ou eliminação
exigem revisão; nomes/atributos fonte não bastam.

## Contrato inerte e estado

Init deve recusar incondicionalmente sem alcançar caller/helper: sem parâmetros,
allocators, endpoints, workers, transporte, MMIO ou chamadas de plataforma.
Preservar CFI estrito, SCS/x18, Full LTO, MODVERSIONS, BTI e retorno PAC.
Assembly manual não recebe automaticamente instrumentação C; conferir
registradores/SP/retorno no ELF futuro. O leaf não deve ganhar calls para
consultar geometria. Carga mesmo com recusa continua proibida.

Revisão textual inicial concluída, mas nenhuma fonte candidata aprovada.
Permanecem retenção comprovada, ABI da geometria, erratas, contexto/mappings/
lifetime e evidência futura de build. Próximo passo: aprofundar a proposta
documental, sem criar candidato ou executar build. Nenhum resultado global PASS,
aquisição de RAM ou autorização operacional. Progresso: ~40% subjetivo.
