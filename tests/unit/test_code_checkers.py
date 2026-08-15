#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CODE 模态查重引擎单测（P3c：code_token / code_template）。

钉死的行为：注释与格式无关性、字面量屏蔽（500 vs 1000 不影响）、
预处理行剔除、字符串感知（"//非注释" 不误杀）、模板样板剔除后
学生逻辑相似度显著低于不剔除（寄存器配置代码查重的核心价值）、
空代码（纯注释）→ 0、CODE 模态隔离。
"""

import algorithms.code  # noqa: F401  (import-time registration side effect)
from algorithms.base import ContentKind
from algorithms.code.code_checkers import (
    normalized_token_string,
    strip_preprocessor,
    tokenize_c,
)
from algorithms.factory import SimilarityCheckerFactory

# --------------------------------------------------------------- tokenizer

def test_strip_preprocessor_drops_directives_only():
    code = "#include \"stm32f4xx.h\"\n#define A 1\n  #define B 2\nint x; // uses #define C\n"
    stripped = strip_preprocessor(code)
    # line-precise: directives dropped, real code kept, and a comment that
    # merely MENTIONS '#define' stays (only leading-# lines are dropped)
    assert stripped.splitlines() == ["int x; // uses #define C"]


def test_tokenizer_masks_literals_and_keeps_identifiers():
    code = 'HAL_Delay(500); status = read("ok"); flag = \'y\';'
    tokens = tokenize_c(code)
    assert "NUM" in tokens and "STR" in tokens and "CHR" in tokens
    assert "HAL_Delay" in tokens and "500" not in tokens
    assert tokenize_c(code, mask_strings=False)[2] == "500"


def test_tokenizer_is_string_aware():
    # '// not a comment' inside a string literal: the string is one token
    # (masked to STR) and the code AFTER it still tokenizes -- proof the
    # scanner did not treat the rest of the line as a comment.
    masked = tokenize_c('printf("// not a comment"); x = 1;')
    assert masked == ["printf", "(", "STR", ")", ";", "x", "=", "NUM", ";"]
    unmasked = tokenize_c('printf("// not a comment"); x = 1;',
                          mask_strings=False)
    assert '"// not a comment"' in unmasked   # token keeps its quotes


def test_tokenizer_strips_line_and_block_comments():
    tokens_a = tokenize_c("int a; /* block */ int b;")
    tokens_b = tokenize_c("int a; // line\nint b;")
    assert tokens_a == tokens_b == tokenize_c("int a; int b;")


def test_comment_only_code_normalizes_to_empty():
    assert normalized_token_string("// nothing here\n/* nothing at all */") == ""


# ------------------------------------------- adversarial-review regressions

def test_unterminated_block_comment_swallows_to_eof():
    # D1 regression: interior must NOT leak as code tokens
    tokens = tokenize_c("int a = 1;\n/* never closed\nint leaked = 42;\n")
    assert tokens == ["int", "a", "=", "NUM", ";"]


def test_unterminated_string_masks_to_end_of_line():
    # D1 regression: unclosed string swallows to EOL as one STR token
    tokens = tokenize_c('printf("never closed; x = 1;\nint ok = 2;\n')
    assert tokens == ["printf", "(", "STR", "int", "ok", "=", "NUM", ";"]


def test_preprocessor_strip_is_comment_aware():
    # D2 regression: '*/' sharing a '#' directive line (commented-out
    # include block) must survive -- otherwise the comment turns
    # unterminated and the rest of the file leaks.
    code = "int a = 1;\n/* commented-out directives\n#endif_of_comment */\nint b = 2;\n"
    assert tokenize_c(code) == ["int", "a", "=", "NUM", ";",
                                "int", "b", "=", "NUM", ";"]


def test_multiline_macro_continuation_lines_dropped():
    code = "#define MAX(a,b) \\\n    ((a) > (b) ? (a) : (b))\nint t = MAX(1,2);\n"
    assert tokenize_c(code) == ["int", "t", "=", "MAX",
                                "(", "NUM", ",", "NUM", ")", ";"]


# ------------------------------------------------------------- code_token

BLINK_A = """
while (1) {
    HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);
    HAL_Delay(500);
}
"""

BLINK_A_REFORMATTED = """
// blink loop with 500ms period
while(1){HAL_GPIO_TogglePin(GPIOA,GPIO_PIN_5);HAL_Delay(500);}
"""

BLINK_A_OTHER_LITERAL = """
#define PERIOD 1000
while (1) {
    HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);
    HAL_Delay(1000);
}
"""

BUTTON_LOGIC = """
while (1) {
    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_0)) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);
    }
}
"""


def _code_token():
    return SimilarityCheckerFactory.create("code_token")


def test_code_token_identical_is_100():
    assert _code_token().score(BLINK_A, BLINK_A) == 100.0


def test_code_token_ignores_comments_and_formatting():
    assert _code_token().score(BLINK_A, BLINK_A_REFORMATTED) == 100.0


def test_code_token_ignores_literal_values():
    assert _code_token().score(BLINK_A, BLINK_A_OTHER_LITERAL) == 100.0


def test_code_token_different_logic_scores_lower():
    score = _code_token().score(BLINK_A, BUTTON_LOGIC)
    assert 0.0 < score < 70.0


def test_code_token_empty_code_scores_zero():
    checker = _code_token()
    assert checker.score("", BLINK_A) == 0.0
    assert checker.score("// only a comment", BLINK_A) == 0.0


def test_code_token_kind_isolation():
    assert "code_token" in SimilarityCheckerFactory.names(ContentKind.CODE)
    assert "code_token" not in SimilarityCheckerFactory.names(ContentKind.TEXT)


def test_code_token_matrix_guarantees():
    checker = _code_token()
    m = checker.compare_matrix([BLINK_A, BLINK_A_REFORMATTED, BUTTON_LOGIC])
    assert m[0][0] == 100.0 and m[1][1] == 100.0
    assert m[0][1] == 100.0
    assert m[0][2] == m[2][0] < 70.0


# ----------------------------------------------------------- code_template

TEMPLATE = """
void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  __HAL_RCC_GPIOA_CLK_ENABLE();
  GPIO_InitStruct.Pin = GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}
int main(void)
{
    HAL_Init();
    MX_GPIO_Init();
"""

STUDENT_A = """
void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  __HAL_RCC_GPIOA_CLK_ENABLE();
  GPIO_InitStruct.Pin = GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}
int main(void)
{
    HAL_Init();
    MX_GPIO_Init();
    while (1) { HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5); HAL_Delay(500); }
}
"""

STUDENT_B = """
void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  __HAL_RCC_GPIOA_CLK_ENABLE();
  GPIO_InitStruct.Pin = GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}
int main(void)
{
    HAL_Init();
    MX_GPIO_Init();
    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_0)) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);
    }
}
"""


def _plain():
    return SimilarityCheckerFactory.create("code_token")


def _templated():
    return SimilarityCheckerFactory.create("code_template",
                                           template_code=TEMPLATE)


def test_template_removal_lowers_cross_student_score():
    """核心价值：共享样板（HAL/寄存器初始化 + main 脚手架）不算抄袭信号。

    实测本语料：81.4（不剔除）→ 55.6（剔除+孤括号行清理后）。残余相似
    度来自两人共用同一 LED（GPIOA/GPIO_PIN_5）与括号结构——控制逻辑不
    同（toggle 循环 vs 按键读取），55.6 正确落在可疑线（60）之下、实
    锤线（85）之外。
    """
    plain = _plain().score(STUDENT_A, STUDENT_B)
    templated = _templated().score(STUDENT_A, STUDENT_B)
    assert templated < plain
    assert templated < 60.0, "shared boilerplate should not reach suspicious line"
    assert templated > 0.0   # same-peripheral logic still shows real overlap


def test_template_identical_work_still_100():
    assert _templated().score(STUDENT_A, STUDENT_A) == 100.0


def test_pure_template_submissions_score_zero():
    """R1 回归：仅模板内容（改了引脚/模式，零学生逻辑）的两份提交
    不得因残留大括号得 100 分——孤括号行剔除后归一化为空 → 0。"""
    tpl_a = TEMPLATE
    tpl_b = (TEMPLATE.replace("GPIO_PIN_5", "GPIO_PIN_7")
                     .replace("GPIO_MODE_OUTPUT_PP", "GPIO_MODE_OUTPUT_OD"))
    assert _templated().score(tpl_a, tpl_b) == 0.0


def test_empty_template_behaves_like_code_token():
    checker = SimilarityCheckerFactory.create("code_template")
    assert checker.score(STUDENT_A, STUDENT_B) == _plain().score(
        STUDENT_A, STUDENT_B)


def test_template_checker_kind_and_registration():
    assert SimilarityCheckerFactory.is_registered("code_template")
    assert "code_template" in SimilarityCheckerFactory.names(ContentKind.CODE)
    assert "code_template" not in SimilarityCheckerFactory.names(
        ContentKind.TEXT)
