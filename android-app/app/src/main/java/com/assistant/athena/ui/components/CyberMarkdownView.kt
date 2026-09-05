package com.assistant.athena.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistant.athena.ui.theme.*

/**
 * High-performance, rich Markdown renderer for ATHENA Library Notes & Chat Messages.
 * Supports:
 * - H1, H2, H3, H4 Headings with visual accents
 * - Blockquotes with teal callout indicators
 * - Bullet and Numbered Lists
 * - Markdown Tables with horizontal scroll
 * - Code Blocks with syntax highlight & copy
 * - Horizontal Dividers (---)
 * - Inline formatting: bold (**), italic (*), code (`), citations ([1])
 */
sealed class MarkdownBlock {
    data class Header(val level: Int, val text: String) : MarkdownBlock()
    data class Blockquote(val text: String) : MarkdownBlock()
    data class BulletList(val items: List<String>) : MarkdownBlock()
    data class NumberedList(val items: List<Pair<String, String>>) : MarkdownBlock()
    data class Table(val headers: List<String>, val rows: List<List<String>>) : MarkdownBlock()
    data class CodeBlock(val language: String, val code: String) : MarkdownBlock()
    object Divider : MarkdownBlock()
    data class Paragraph(val text: String) : MarkdownBlock()
}

@Composable
fun CyberMarkdownView(
    text: String,
    modifier: Modifier = Modifier,
    onCopyCode: (String) -> Unit = {}
) {
    val blocks = remember(text) { parseFullMarkdown(text) }

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        blocks.forEach { block ->
            when (block) {
                is MarkdownBlock.Header -> {
                    when (block.level) {
                        1 -> {
                            Text(
                                text = formatInlineMarkdown(block.text),
                                color = TextPrimary,
                                fontSize = 19.sp,
                                fontWeight = FontWeight.Bold,
                                lineHeight = 26.sp,
                                modifier = Modifier.padding(top = 10.dp, bottom = 4.dp)
                            )
                        }
                        2 -> {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.padding(top = 10.dp, bottom = 2.dp)
                            ) {
                                Box(
                                    modifier = Modifier
                                        .width(3.5.dp)
                                        .height(18.dp)
                                        .background(PerplexityTeal, RoundedCornerShape(2.dp))
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = formatInlineMarkdown(block.text),
                                    color = TextPrimary,
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.Bold,
                                    lineHeight = 22.sp
                                )
                            }
                        }
                        3 -> {
                            Text(
                                text = formatInlineMarkdown(block.text),
                                color = Color(0xFFE4E4E7),
                                fontSize = 14.5.sp,
                                fontWeight = FontWeight.SemiBold,
                                lineHeight = 20.sp,
                                modifier = Modifier.padding(top = 6.dp, bottom = 2.dp)
                            )
                        }
                        else -> {
                            Text(
                                text = formatInlineMarkdown(block.text),
                                color = TextSecondary,
                                fontSize = 13.5.sp,
                                fontWeight = FontWeight.Bold,
                                lineHeight = 19.sp,
                                modifier = Modifier.padding(top = 4.dp)
                            )
                        }
                    }
                }

                is MarkdownBlock.Blockquote -> {
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp),
                        color = Color(0xFF141416),
                        shape = RoundedCornerShape(topEnd = 8.dp, bottomEnd = 8.dp),
                        border = BorderStroke(0.5.dp, Color(0xFF262628))
                    ) {
                        Row(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
                            Box(
                                modifier = Modifier
                                    .width(3.dp)
                                    .height(20.dp)
                                    .background(PerplexityTeal, RoundedCornerShape(2.dp))
                            )
                            Spacer(modifier = Modifier.width(10.dp))
                            Text(
                                text = formatInlineMarkdown(block.text),
                                color = Color(0xFFD1D5DB),
                                fontSize = 13.sp,
                                fontStyle = FontStyle.Italic,
                                lineHeight = 19.sp
                            )
                        }
                    }
                }

                is MarkdownBlock.Divider -> {
                    HorizontalDivider(
                        modifier = Modifier.padding(vertical = 6.dp),
                        color = Color(0xFF2E2E32),
                        thickness = 1.dp
                    )
                }

                is MarkdownBlock.BulletList -> {
                    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        block.items.forEach { item ->
                            Row(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = "•",
                                    color = PerplexityTeal,
                                    fontSize = 15.sp,
                                    modifier = Modifier.padding(end = 8.dp, top = 0.dp)
                                )
                                Text(
                                    text = formatInlineMarkdown(item),
                                    color = TextPrimary,
                                    fontSize = 13.5.sp,
                                    lineHeight = 20.sp,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }
                }

                is MarkdownBlock.NumberedList -> {
                    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        block.items.forEach { (num, item) ->
                            Row(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = "$num.",
                                    color = PerplexityTeal,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 12.5.sp,
                                    modifier = Modifier.width(22.dp)
                                )
                                Text(
                                    text = formatInlineMarkdown(item),
                                    color = TextPrimary,
                                    fontSize = 13.5.sp,
                                    lineHeight = 20.sp,
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }
                }

                is MarkdownBlock.Table -> {
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 6.dp),
                        color = Color(0xFF141416),
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(0.5.dp, Color(0xFF2A2A2E))
                    ) {
                        Box(modifier = Modifier.horizontalScroll(rememberScrollState())) {
                            Column {
                                // Header row
                                Row(
                                    modifier = Modifier
                                        .background(Color(0xFF1F1F24))
                                        .padding(vertical = 8.dp, horizontal = 4.dp)
                                ) {
                                    block.headers.forEach { h ->
                                        Box(
                                            modifier = Modifier
                                                .widthIn(min = 90.dp, max = 200.dp)
                                                .padding(horizontal = 8.dp)
                                        ) {
                                            Text(
                                                text = formatInlineMarkdown(h),
                                                color = TextPrimary,
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 12.sp,
                                                maxLines = 2,
                                                overflow = TextOverflow.Ellipsis
                                            )
                                        }
                                    }
                                }
                                HorizontalDivider(color = Color(0xFF2A2A2E), thickness = 1.dp)

                                // Rows
                                block.rows.forEachIndexed { idx, row ->
                                    val bg = if (idx % 2 == 0) Color(0xFF141416) else Color(0xFF18181B)
                                    Row(
                                        modifier = Modifier
                                            .background(bg)
                                            .padding(vertical = 8.dp, horizontal = 4.dp)
                                    ) {
                                        row.forEach { cell ->
                                            Box(
                                                modifier = Modifier
                                                    .widthIn(min = 90.dp, max = 200.dp)
                                                    .padding(horizontal = 8.dp)
                                            ) {
                                                Text(
                                                    text = formatInlineMarkdown(cell),
                                                    color = Color(0xFFD4D4D8),
                                                    fontSize = 12.sp,
                                                    lineHeight = 17.sp
                                                )
                                            }
                                        }
                                    }
                                    if (idx < block.rows.size - 1) {
                                        HorizontalDivider(color = Color(0xFF222226), thickness = 0.5.dp)
                                    }
                                }
                            }
                        }
                    }
                }

                is MarkdownBlock.CodeBlock -> {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        color = VoidBlack,
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, PanelStroke)
                    ) {
                        Column {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .background(PanelDarkSolid)
                                    .padding(horizontal = 10.dp, vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = block.language.ifBlank { "CODE" }.uppercase(),
                                    color = NeonCyan,
                                    fontSize = 10.sp,
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold
                                )
                                Row(
                                    modifier = Modifier
                                        .clickable { onCopyCode(block.code) }
                                        .padding(4.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.ContentCopy,
                                        contentDescription = "Copy code",
                                        tint = TextMuted,
                                        modifier = Modifier.size(12.dp)
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(
                                        text = "COPY",
                                        color = TextMuted,
                                        fontSize = 10.sp,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                            }
                            Text(
                                text = block.code,
                                color = NeonCyanLight,
                                fontSize = 12.sp,
                                fontFamily = FontFamily.Monospace,
                                lineHeight = 17.sp,
                                modifier = Modifier.padding(10.dp)
                            )
                        }
                    }
                }

                is MarkdownBlock.Paragraph -> {
                    Text(
                        text = formatInlineMarkdown(block.text),
                        color = TextPrimary,
                        fontSize = 13.5.sp,
                        lineHeight = 20.5.sp
                    )
                }
            }
        }
    }
}

/**
 * Robust line-based Markdown parser that handles headers, tables, blockquotes,
 * bullet lists, numbered lists, dividers, and code blocks.
 */
fun parseFullMarkdown(rawText: String): List<MarkdownBlock> {
    val result = mutableListOf<MarkdownBlock>()
    val lines = rawText.lines()
    var i = 0

    while (i < lines.size) {
        val line = lines[i]
        val trimmed = line.trim()

        if (trimmed.isEmpty()) {
            i++
            continue
        }

        // 1. Code block
        if (trimmed.startsWith("```")) {
            val lang = trimmed.removePrefix("```").trim()
            val codeLines = mutableListOf<String>()
            i++
            while (i < lines.size && !lines[i].trim().startsWith("```")) {
                codeLines.add(lines[i])
                i++
            }
            if (i < lines.size) i++ // skip closing ```
            result.add(MarkdownBlock.CodeBlock(lang, codeLines.joinToString("\n")))
            continue
        }

        // 2. Table (| Col | Col |)
        if (trimmed.startsWith("|") && trimmed.endsWith("|") && i + 1 < lines.size) {
            val nextTrimmed = lines[i + 1].trim()
            if (nextTrimmed.startsWith("|") && nextTrimmed.contains("---")) {
                val headers = trimmed.split("|").map { it.trim() }.filter { it.isNotEmpty() }
                i += 2 // skip header and separator
                val tableRows = mutableListOf<List<String>>()
                while (i < lines.size) {
                    val rLine = lines[i].trim()
                    if (!rLine.startsWith("|") || !rLine.endsWith("|")) break
                    val cells = rLine.split("|").map { it.trim() }.drop(1).dropLast(1)
                    if (cells.isNotEmpty()) tableRows.add(cells)
                    i++
                }
                result.add(MarkdownBlock.Table(headers, tableRows))
                continue
            }
        }

        // 3. Headings
        if (trimmed.startsWith("#")) {
            val hashCount = trimmed.takeWhile { it == '#' }.length
            val headerText = trimmed.removePrefix("#".repeat(hashCount)).trim()
            if (hashCount in 1..4 && headerText.isNotEmpty()) {
                result.add(MarkdownBlock.Header(hashCount, headerText))
                i++
                continue
            }
        }

        // 4. Horizontal Rule
        if (trimmed == "---" || trimmed == "***" || trimmed == "___") {
            result.add(MarkdownBlock.Divider)
            i++
            continue
        }

        // 5. Blockquote
        if (trimmed.startsWith(">")) {
            val quoteLines = mutableListOf<String>()
            while (i < lines.size) {
                val qLine = lines[i].trim()
                if (!qLine.startsWith(">")) break
                quoteLines.add(qLine.removePrefix(">").trim())
                i++
            }
            result.add(MarkdownBlock.Blockquote(quoteLines.joinToString(" ")))
            continue
        }

        // 6. Bullet List (- item or * item)
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
            val listItems = mutableListOf<String>()
            while (i < lines.size) {
                val bLine = lines[i].trim()
                if (!bLine.startsWith("- ") && !bLine.startsWith("* ")) break
                listItems.add(bLine.substring(2).trim())
                i++
            }
            result.add(MarkdownBlock.BulletList(listItems))
            continue
        }

        // 7. Numbered List (1. item)
        val numMatch = Regex("^(\\d+)\\.\\s+(.*)$").find(trimmed)
        if (numMatch != null) {
            val listItems = mutableListOf<Pair<String, String>>()
            while (i < lines.size) {
                val nLine = lines[i].trim()
                val m = Regex("^(\\d+)\\.\\s+(.*)$").find(nLine) ?: break
                listItems.add(Pair(m.groupValues[1], m.groupValues[2]))
                i++
            }
            result.add(MarkdownBlock.NumberedList(listItems))
            continue
        }

        // 8. Regular Paragraph
        val paraLines = mutableListOf<String>()
        while (i < lines.size) {
            val pLine = lines[i].trim()
            if (pLine.isEmpty() ||
                pLine.startsWith("```") ||
                pLine.startsWith("#") ||
                pLine == "---" || pLine == "***" ||
                pLine.startsWith(">") ||
                pLine.startsWith("- ") || pLine.startsWith("* ") ||
                Regex("^(\\d+)\\.\\s+").containsMatchIn(pLine) ||
                (pLine.startsWith("|") && pLine.endsWith("|"))
            ) {
                break
            }
            paraLines.add(pLine)
            i++
        }
        if (paraLines.isNotEmpty()) {
            result.add(MarkdownBlock.Paragraph(paraLines.joinToString(" ")))
        }
    }

    return result
}

/**
 * Inline Markdown formatter:
 * Handles **bold**, *italic*, `code`, and [1] citations.
 */
fun formatInlineMarkdown(text: String): AnnotatedString {
    return buildAnnotatedString {
        var cursor = 0
        // Match code, bold, italic, or citations
        val regex = Regex("(`[^`]+`)|(\\*{2}[^*]+\\*{2})|(\\*[^*]+\\*)|(\\[\\d+\\])|(\\[([^\\]]+)\\]\\(([^\\)]+)\\))")
        val matches = regex.findAll(text)

        for (match in matches) {
            val range = match.range
            if (range.first > cursor) {
                append(text.substring(cursor, range.first))
            }

            val v = match.value
            when {
                v.startsWith("`") && v.endsWith("`") -> {
                    val codeContent = v.removePrefix("`").removeSuffix("`")
                    withStyle(
                        SpanStyle(
                            fontFamily = FontFamily.Monospace,
                            color = NeonCyan,
                            background = NeonCyanDim
                        )
                    ) {
                        append(" $codeContent ")
                    }
                }
                v.startsWith("**") && v.endsWith("**") -> {
                    val boldContent = v.removePrefix("**").removeSuffix("**")
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = TextPrimary)) {
                        append(boldContent)
                    }
                }
                v.startsWith("*") && v.endsWith("*") -> {
                    val italicContent = v.removePrefix("*").removeSuffix("*")
                    withStyle(SpanStyle(fontStyle = FontStyle.Italic, color = TextSecondary)) {
                        append(italicContent)
                    }
                }
                v.startsWith("[") && v.endsWith("]") && v.drop(1).dropLast(1).all { it.isDigit() } -> {
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = PerplexityTeal)) {
                        append(v)
                    }
                }
                v.startsWith("[") && v.contains("](") -> {
                    val label = v.substringAfter("[").substringBefore("]")
                    withStyle(SpanStyle(color = PerplexityTeal, textDecoration = TextDecoration.Underline)) {
                        append(label)
                    }
                }
                else -> {
                    append(v)
                }
            }
            cursor = range.last + 1
        }

        if (cursor < text.length) {
            append(text.substring(cursor))
        }
    }
}
