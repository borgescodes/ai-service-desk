# Equivalencia do motor 2.1

Este documento registra o destino de cada um dos 75 testes coletados no motor local 2.1 antes da migracao. O numero 75 e um baseline historico, nao uma meta numerica para a suite nova. O criterio de aceite e preservar os contratos relevantes da spec da Fase 1.

Status usados:

- `MIGRADO`: o mesmo comportamento observavel possui teste direto no pacote oficial.
- `SUBSTITUIDO_POR_TESTE_EQUIVALENTE`: a estrutura interna mudou, mas o contrato e verificado por um teste equivalente ou mais forte.
- `FORA_DE_ESCOPO`: comportamento deliberadamente reservado para outra fase.
- `OBSOLETO_COM_JUSTIFICATIVA`: comportamento antigo nao deve ser preservado e a justificativa esta registrada.

Nenhum teste foi classificado como `FORA_DE_ESCOPO` sem cobertura do risco correspondente nesta fase.

| Legacy node id | Status | New test or justification |
| --- | --- | --- |
| `test_busca_core.py::BuscaCoreTests::test_carregar_amostra_valida_campos_e_remove_texto_vazio` | `SUBSTITUIDO_POR_TESTE_EQUIVALENTE` | `tests/engine/test_data.py::test_load_corpus_rejects_duplicate_empty_and_missing_values` - `load_corpus` agora rejeita `texto_busca` vazio em vez de descartá-lo silenciosamente. |
| `test_busca_core.py::BuscaCoreTests::test_normalizar_matriz_produz_norma_um` | `MIGRADO` | `tests/engine/test_validation.py::test_normalize_matrix_returns_float32_unit_vectors` |
| `test_busca_core.py::BuscaCoreTests::test_top_k_indices_ordena_maiores_scores` | `SUBSTITUIDO_POR_TESTE_EQUIVALENTE` | `tests/engine/test_retrieval.py::test_threshold_filter_orders_descending` - O helper isolado `top_k_indices` deixou de ser contrato público; ordenação é coberta no filtro por threshold. |
| `test_busca_core.py::ContextoBuscaTests::test_intent_impressao_pode_restringir_pool_sem_sistema` | `MIGRADO` | `tests/engine/test_retrieval.py::test_intent_can_restrict_pool_when_it_has_enough_matches` |
| `test_busca_core.py::ContextoBuscaTests::test_limiar_pode_retornar_vazio` | `MIGRADO` | `tests/engine/test_retrieval.py::test_no_evidence_when_scores_are_below_threshold` |
| `test_busca_core.py::ContextoBuscaTests::test_limiar_remove_resultados_fracos_e_ordena` | `MIGRADO` | `tests/engine/test_retrieval.py::test_threshold_filter_orders_descending` |
| `test_busca_core.py::ContextoBuscaTests::test_sistema_com_massa_suficiente_restringe_pool` | `SUBSTITUIDO_POR_TESTE_EQUIVALENTE` | `tests/engine/test_retrieval.py::test_wrong_system_is_excluded_even_when_highest_score` - A barreira de sistema é comprovada no resultado final, não apenas no helper de pool. |
| `test_busca_core.py::ContextoBuscaTests::test_sistema_sem_massa_suficiente_faz_fallback` | `SUBSTITUIDO_POR_TESTE_EQUIVALENTE` | `tests/engine/test_retrieval.py::test_sparse_context_still_blocks_other_system` - O fallback exploratório legado foi endurecido: contexto escasso nunca promove outro sistema. |
| `test_classificacao.py::ClassificacaoTests::test_payload_desliga_thinking_e_define_schema` | `MIGRADO` | `tests/engine/test_classification.py::test_payload_disables_thinking_and_closes_schema` |
| `test_classificacao.py::ClassificacaoTests::test_rejeita_confidence_fora_do_intervalo` | `MIGRADO` | `tests/engine/test_classification.py::test_validate_classification_rejects_contract_violations[bad6]` |
| `test_classificacao.py::ClassificacaoTests::test_rejeita_intent_fora_do_contrato` | `MIGRADO` | `tests/engine/test_classification.py::test_validate_classification_rejects_contract_violations[bad0]` |
| `test_classificacao.py::ClassificacaoTests::test_sistema_desconhecido_pode_ser_preservado_sem_mapear` | `MIGRADO` | `tests/engine/test_classification.py::test_validate_classification_accepts_unknown_literal_system` |
| `test_classificacao.py::ClassificacaoTests::test_valida_classificacao_cigam` | `SUBSTITUIDO_POR_TESTE_EQUIVALENTE` | `tests/engine/test_validation.py::test_ticket_classification_preserves_contract` - O dataclass oficial e o contrato validado são testados separadamente. |
| `test_classificacao.py::ClassificacaoHttpTests::test_classificar_ticket_converte_resposta_do_ollama` | `MIGRADO` | `tests/engine/test_ollama.py::test_classifier_runs_through_real_http_boundary` |
| `test_classificacao.py::ClassificacaoRegressaoSistemaTests::test_preserva_cigam_explicito_quando_modelo_omite_system` | `MIGRADO` | `tests/engine/test_classification.py::test_explicit_cigam_overrides_invented_model_system_and_routine` |
| `tests/test_cli.py::CliTests::test_bad_index_returns_error_not_traceback` | `MIGRADO` | `tests/test_cli.py::test_missing_index_returns_error_without_traceback` |
| `tests/test_cli.py::CliTests::test_check_data_command_uses_bundled_sample` | `SUBSTITUIDO_POR_TESTE_EQUIVALENTE` | `tests/test_cli.py::test_inspect_uses_synthetic_fixture_without_history` - A amostra corporativa legada foi substituída por fixture 100% sintética. |
| `tests/test_cli.py::CliTests::test_help_runs_without_ollama` | `MIGRADO` | `tests/test_cli.py::test_help_runs_without_ollama` |
| `tests/test_cli.py::CliTests::test_validation_writes_report_on_connection_failure` | `MIGRADO` | `tests/engine/test_smoke.py::test_validation_writes_report_when_ollama_fails` |
| `tests/test_contracts.py::ContractsTests::test_chat_is_short_non_thinking_and_low_temperature` | `MIGRADO` | `tests/engine/test_classification.py::test_payload_disables_thinking_and_closes_schema` |
| `tests/test_contracts.py::ContractsTests::test_cigam_explicit_overrides_invented_system` | `MIGRADO` | `tests/engine/test_classification.py::test_explicit_cigam_overrides_invented_model_system_and_routine` |
| `tests/test_contracts.py::ContractsTests::test_confidence_boolean_rejected` | `MIGRADO` | `tests/engine/test_classification.py::test_validate_classification_rejects_contract_violations[bad3]` |
| `tests/test_contracts.py::ContractsTests::test_empty_input_is_rejected_before_http` | `MIGRADO` | `tests/engine/test_classification.py::test_build_payload_rejects_invalid_input_before_transport` |
| `tests/test_contracts.py::ContractsTests::test_literal_unknown_system_preserved` | `MIGRADO` | `tests/engine/test_classification.py::test_explicit_unknown_system_is_preserved_from_literal_text` |
| `tests/test_contracts.py::ContractsTests::test_multiple_systems_do_not_choose_arbitrarily` | `MIGRADO` | `tests/engine/test_classification.py::test_multiple_explicit_systems_are_ambiguous` |
| `tests/test_contracts.py::ContractsTests::test_nan_vectors_rejected` | `MIGRADO` | `tests/engine/test_validation.py::test_normalize_matrix_rejects_invalid_vectors[matrix2]` |
| `tests/test_contracts.py::ContractsTests::test_non_string_entity_rejected` | `MIGRADO` | `tests/engine/test_classification.py::test_validate_classification_rejects_contract_violations[bad2]` |
| `tests/test_contracts.py::ContractsTests::test_one_dimensional_matrix_rejected` | `MIGRADO` | `tests/engine/test_validation.py::test_normalize_matrix_rejects_invalid_vectors[matrix0]` |
| `tests/test_contracts.py::ContractsTests::test_routine_not_fabricated` | `MIGRADO` | `tests/engine/test_classification.py::test_routine_is_not_fabricated_without_literal_evidence` |
| `tests/test_contracts.py::ContractsTests::test_siagri_is_also_preserved` | `MIGRADO` | `tests/engine/test_classification.py::test_siagri_literal_is_preserved` |
| `tests/test_contracts.py::ContractsTests::test_system_null_is_not_string_none` | `MIGRADO` | `tests/engine/test_classification.py::test_validate_classification_rejects_contract_violations[bad1]` |
| `tests/test_contracts.py::ContractsTests::test_unmentioned_system_is_removed` | `MIGRADO` | `tests/engine/test_classification.py::test_invented_system_is_removed_when_not_literal` |
| `tests/test_contracts.py::ContractsTests::test_word_boundary_does_not_match_supercigam` | `MIGRADO` | `tests/engine/test_classification.py::test_supercigam_does_not_match_cigam_alias` |
| `tests/test_contracts.py::ContractsTests::test_zero_vector_rejected` | `MIGRADO` | `tests/engine/test_validation.py::test_normalize_matrix_rejects_invalid_vectors[matrix1]` |
| `tests/test_contracts.py::UnknownSystemRegressionTests::test_explicit_unknown_survives_model_omission` | `MIGRADO` | `tests/engine/test_classification.py::test_explicit_unknown_system_is_preserved_from_literal_text` |
| `tests/test_contracts.py::MoreGroundingTests::test_equipment_is_not_a_software_system` | `MIGRADO` | `tests/engine/test_classification.py::test_equipment_name_is_not_promoted_to_software_system` |
| `tests/test_contracts.py::MoreGroundingTests::test_generic_system_word_does_not_hide_explicit_unknown_name` | `MIGRADO` | `tests/engine/test_classification.py::test_explicit_unknown_system_is_preserved_from_literal_text` |
| `tests/test_data.py::DataTests::test_clean_html_and_controls` | `MIGRADO` | `tests/engine/test_data.py::test_clean_text_removes_html_scripts_and_controls` |
| `tests/test_data.py::DataTests::test_duplicate_ids_rejected` | `MIGRADO` | `tests/engine/test_data.py::test_load_corpus_rejects_duplicate_empty_and_missing_values` |
| `tests/test_data.py::DataTests::test_load_keeps_ids_as_text_and_problem_separate` | `MIGRADO` | `tests/engine/test_data.py::test_load_corpus_preserves_text_ids_and_marks_history` |
| `tests/test_data.py::DataTests::test_missing_columns_rejected` | `MIGRADO` | `tests/engine/test_data.py::test_load_corpus_rejects_duplicate_empty_and_missing_values` |
| `tests/test_data.py::DataTests::test_orphan_notes_are_reported_not_joined` | `MIGRADO` | `tests/engine/test_data.py::test_prepare_orders_notes_filters_status_scope_and_sensitive` |
| `tests/test_data.py::DataTests::test_prepare_joins_in_order_and_filters_closed_cancelled` | `MIGRADO` | `tests/engine/test_data.py::test_prepare_orders_notes_filters_status_scope_and_sensitive` |
| `tests/test_data.py::DataTests::test_sanitization_preserves_domain_and_masks_contacts` | `MIGRADO` | `tests/engine/test_data.py::test_sanitize_masks_contacts_but_preserves_system_name` |
| `tests/test_data.py::DataTests::test_sensitive_filter_is_conservative` | `MIGRADO` | `tests/engine/test_data.py::test_sensitive_filter_is_conservative` |
| `tests/test_http_engine.py::HttpTests::test_batch_embedding_validated_and_normalized` | `MIGRADO` | `tests/engine/test_ollama.py::test_batch_embedding_is_normalized_and_disables_truncation` |
| `tests/test_http_engine.py::HttpTests::test_cloud_model_refused` | `MIGRADO` | `tests/engine/test_ollama.py::test_invalid_embedding_redirect_malformed_json_and_cloud_are_refused` |
| `tests/test_http_engine.py::HttpTests::test_malformed_json_refused` | `MIGRADO` | `tests/engine/test_ollama.py::test_invalid_embedding_redirect_malformed_json_and_cloud_are_refused` |
| `tests/test_http_engine.py::HttpTests::test_missing_model_returns_actionable_error` | `MIGRADO` | `tests/engine/test_ollama.py::test_models_version_and_missing_model` |
| `tests/test_http_engine.py::HttpTests::test_models_and_version_read` | `MIGRADO` | `tests/engine/test_ollama.py::test_models_version_and_missing_model` |
| `tests/test_http_engine.py::HttpTests::test_proxy_environment_not_used` | `MIGRADO` | `tests/engine/test_ollama.py::test_proxy_environment_is_disabled` |
| `tests/test_http_engine.py::HttpTests::test_redirect_refused` | `MIGRADO` | `tests/engine/test_ollama.py::test_invalid_embedding_redirect_malformed_json_and_cloud_are_refused` |
| `tests/test_http_engine.py::HttpTests::test_remote_host_refused` | `MIGRADO` | `tests/engine/test_ollama.py::test_remote_and_malformed_base_urls_are_refused` |
| `tests/test_http_engine.py::HttpTests::test_utf8_classifier_via_real_http_boundary` | `MIGRADO` | `tests/engine/test_ollama.py::test_classifier_runs_through_real_http_boundary` |
| `tests/test_http_engine.py::HttpTests::test_zero_embedding_refused` | `MIGRADO` | `tests/engine/test_ollama.py::test_invalid_embedding_redirect_malformed_json_and_cloud_are_refused` |
| `tests/test_http_engine.py::RetrievalTests::test_dimensions_checked` | `MIGRADO` | `tests/engine/test_retrieval.py::test_dimensions_and_parameters_are_validated` |
| `tests/test_http_engine.py::RetrievalTests::test_formatter_does_not_claim_verified_solution_or_probability` | `MIGRADO` | `tests/engine/test_retrieval.py::test_formatter_never_claims_verified_solution_or_prints_history_by_default` |
| `tests/test_http_engine.py::RetrievalTests::test_history_does_not_affect_ranking` | `MIGRADO` | `tests/engine/test_retrieval.py::test_history_does_not_affect_ranking` |
| `tests/test_http_engine.py::RetrievalTests::test_no_evidence_when_scores_below_threshold` | `MIGRADO` | `tests/engine/test_retrieval.py::test_no_evidence_when_scores_are_below_threshold` |
| `tests/test_http_engine.py::RetrievalTests::test_sensitive_history_not_exposed_as_candidate` | `MIGRADO` | `tests/engine/test_retrieval.py::test_sensitive_history_is_not_exposed_as_candidate` |
| `tests/test_http_engine.py::RetrievalTests::test_sparse_context_still_blocks_office` | `MIGRADO` | `tests/engine/test_retrieval.py::test_sparse_context_still_blocks_other_system` |
| `tests/test_http_engine.py::RetrievalTests::test_two_explicit_systems_request_clarification` | `MIGRADO` | `tests/engine/test_retrieval.py::test_two_explicit_systems_return_ambiguous` |
| `tests/test_http_engine.py::RetrievalTests::test_unknown_system_never_maps_to_another` | `MIGRADO` | `tests/engine/test_retrieval.py::test_unknown_system_never_maps_to_another` |
| `tests/test_http_engine.py::RetrievalTests::test_wrong_system_excluded_even_if_highest_score` | `MIGRADO` | `tests/engine/test_retrieval.py::test_wrong_system_is_excluded_even_when_highest_score` |
| `tests/test_index.py::IndexTests::test_build_and_load_preserves_alignment` | `MIGRADO` | `tests/engine/test_index.py::test_build_and_load_preserve_alignment_and_manifest` |
| `tests/test_index.py::IndexTests::test_changed_corpus_cannot_resume` | `MIGRADO` | `tests/engine/test_index.py::test_incomplete_changed_corrupt_and_digest_mismatch_are_refused` |
| `tests/test_index.py::IndexTests::test_completed_index_does_not_call_embedding` | `MIGRADO` | `tests/engine/test_index.py::test_completed_index_does_not_reembed` |
| `tests/test_index.py::IndexTests::test_corrupt_vectors_refused` | `MIGRADO` | `tests/engine/test_index.py::test_incomplete_changed_corrupt_and_digest_mismatch_are_refused` |
| `tests/test_index.py::IndexTests::test_import_legacy_rejects_different_vectors` | `MIGRADO` | `tests/engine/test_index.py::test_import_legacy_rejects_different_vectors` |
| `tests/test_index.py::IndexTests::test_import_legacy_uses_real_sentinels` | `MIGRADO` | `tests/engine/test_index.py::test_import_legacy_uses_three_sentinels_and_new_destination` |
| `tests/test_index.py::IndexTests::test_incomplete_index_cannot_be_searched` | `MIGRADO` | `tests/engine/test_index.py::test_incomplete_changed_corrupt_and_digest_mismatch_are_refused` |
| `tests/test_index.py::IndexTests::test_model_digest_mismatch_refused` | `MIGRADO` | `tests/engine/test_index.py::test_incomplete_changed_corrupt_and_digest_mismatch_are_refused` |
| `tests/test_index.py::IndexTests::test_resume_does_not_repeat_committed_batch` | `MIGRADO` | `tests/engine/test_index.py::test_resume_does_not_repeat_committed_batch` |
| `tests/test_index.py::IndexTests::test_wrong_batch_shape_is_not_committed` | `MIGRADO` | `tests/engine/test_index.py::test_batch_size_and_wrong_shape_are_refused` |
| `tests/test_integrated.py::PipelineIntegrationTests::test_http_index_classifier_context_and_ranking_connected` | `MIGRADO` | `tests/engine/test_ollama.py::test_http_pipeline_connects_classifier_index_and_retrieval` |
