# Coletor de mapas com procedência de boot

**Atualização:** a primeira coleta real no Quest passou em 2026-11-17;
[resultado e limites](2026-11-17-memory-map-device-result.md). O estado sem
aparelho e sem validação do transporte abaixo descreve a preparação histórica.

**Coletor implementado e testado no host; ainda não usado no Quest.** O ADB
continua sem aparelho autorizado conectado nesta etapa. Não houve nova captura,
carga de módulo, pausa de CPUs, reserva de páginas ou reset.

## Escopo fixo

`tools/collect-memory-maps.py` lê, nesta ordem: boot ID inicial, identidade,
release, tamanho de página, compatible do DT vivo, FDT binário, iomem,
zoneinfo, pagetypeinfo e boot ID final. Não aceita comandos ou caminhos remotos
arbitrários. Não lê conteúdo de RAM física, não monta debugfs, não instala root,
não executa `adb root` e não repete tentativas de root/reset.

O modo `--root` usa somente o `su` **já disponível**, com o payload completo
de `su -c` cotado para preservar seu argumento através do ADB. Sem essa opção,
tenta as mesmas leituras como usuário do transporte. Não há fallback automático
que altere permissões ou configurações quando uma leitura falha.

## Contrato de captura

- Recusa aparelho ausente, não autorizado ou seleção ambígua antes de criar saída.
- `--serial` permite escolher um aparelho já autorizado, sem registrar seu serial.
- Cria diretório novo, com modo 0700; recusa saída existente sem sobrescrevê-la.
- Salva stdout binário e stderr de cada leitura, tamanhos, SHA-256 e retorno.
- Timeout de 30 segundos por comando, sem retry; preserva bytes parciais e
  tenta a leitura final do boot mesmo após falhas intermediárias.
- Mantém manifesto incremental e rejeita captura incompleta, vazia ou com falhas.
- Exige boot IDs válidos e iguais, release stock esperado, páginas de 4 KiB,
  pageblock_order=10 e 1.024 páginas/bloco. Confere cabeçalho de zoneinfo,
  tamanho exato/FDT/compatible e parsing DT/iomem pelo planner existente.
- Recusa mapas zerados, DT truncado/com bytes extras, board incompatível ou
  geometria não suportada; retorna código 2 para captura rejeitada.

Boot IDs iguais comprovam somente as extremidades da coleta. Metadados foram
lidos separadamente: não são snapshot atômico, reserva ou proteção de lifetime.
`captured-and-validated` significa captura consistente no escopo acima, **não**
RAM disponível, reservas dinâmicas resolvidas ou prontidão para boot.

## Uso após reconectar, com Android/root estáveis

Na raiz do projeto, depois de confirmar um único Quest autorizado no ADB:

```sh
python3 tools/collect-memory-maps.py --root
```

Por padrão, a saída fica em um novo
`private-diagnostics/memory-maps-<data-UTC>/`, ignorado pelo Git. É possível
indicar outro diretório novo com `--out`; manter evidência bruta em local privado.
Os arquivos boot-before/after contêm UUIDs e outros brutos podem conter dados
identificáveis. O manifesto omite serial e valores de boot ID, mas não deve ser
publicado automaticamente sem revisão.

Não executar tentativas adicionais de root, resets ou alterações de serviços
apenas para obter esta coleta. Se `su` não estiver estável, parar e preservar
as evidências. Nenhum teste de CPU ou aquisição acompanha o coletor.

## Testes e limites

`tools/test-memory-map-collector.py` usa exclusivamente executável ADB falso e
DT sintético. Exercita seleção de dispositivo, quoting remoto, opção root,
binário intacto/hashes, privacidade do manifesto, saída existente, mudança ou
UUID inválido de boot, release/página/pageblock inesperados, DT ruim/ruído,
compatible divergente, iomem ocultado, erro de leitura, timeout e falha ao
iniciar subprocesso. Saída parcial permanece rejeitada, com boot final tentado.

Os validadores também aceitaram os metadados históricos preservados, offline;
essa checagem não foi uma nova captura nem valida o transporte real.
Suíte host: **34 aprovações, zero falhas ou testes ignorados**.

As 13 reservas dinâmicas e a geometria histórica continuam com os limites do
[relatório anterior](2026-11-17-memory-survey-planning.md). Só após nova captura
consistente será possível revisar uma sondagem pequena. Pausas de CPUs e
aquisição de páginas continuam exigindo plano e autorização separados.
