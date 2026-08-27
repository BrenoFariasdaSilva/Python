import unittest  # Load standard-library regression framework.
from pathlib import Path  # Build inert media paths for planning tests.

from correct_report_track_metadata import MovieReportEntry, StreamSnapshot, build_progress_media_path, parse_audio_report_track, parse_subtitle_report_track, plan_audio_metadata_edits, plan_subtitle_metadata_edits, normalize_language_value, select_default_audio_track, WorkflowSummary  # Import tested workflow pieces.


class CorrectReportTrackMetadataTests(unittest.TestCase):  # Group report metadata correction regressions.
    def test_audio_prefix_wins_over_existing_title(self) -> None:  # Cover report prefix priority.
        track = parse_audio_report_track("Brazilian Portuguese (por) - Portuguese (Default)", 0)  # Parse Portuguese-title report row.
        self.assertEqual(track.language, "Brazilian Portuguese")  # Assert PT-BR language survives title.
        self.assertEqual(track.target_name, "Brazilian Portuguese")  # Assert target name follows canonical language.

    def test_audio_prefix_is_case_insensitive(self) -> None:  # Cover mixed-case prefix.
        track = parse_audio_report_track("BRAZILIAN PORTUGUESE (POR) - PORTUGUESE (Default)", 0)  # Parse uppercase report row.
        self.assertEqual(track.language, "Brazilian Portuguese")  # Assert uppercase PT-BR normalizes.

    def test_pt_br_prefix_with_generic_parenthesis(self) -> None:  # Cover PT-BR plus generic code.
        track = parse_audio_report_track("pt-br (por) - Português", 0)  # Parse PT-BR report row.
        self.assertEqual(track.language, "Brazilian Portuguese")  # Assert PT-BR indicator wins.

    def test_portugues_brasil_prefix(self) -> None:  # Cover accented Brazil marker.
        track = parse_audio_report_track("Português Brasil (por)", 0)  # Parse Portuguese Brazil report row.
        self.assertEqual(track.language, "Brazilian Portuguese")  # Assert Brazil marker wins.

    def test_generic_portuguese_parenthesis_stays_generic(self) -> None:  # Cover generic Portuguese.
        track = parse_audio_report_track("Portuguese (por)", 0)  # Parse generic Portuguese report row.
        self.assertEqual(track.language, "Portuguese")  # Assert generic Portuguese stays generic.

    def test_generic_por_title_stays_generic(self) -> None:  # Cover raw generic code.
        track = parse_audio_report_track("por - Portuguese", 0)  # Parse generic raw-code report row.
        self.assertEqual(track.language, "Portuguese")  # Assert generic code stays generic.

    def test_unique_english_candidate_selected(self) -> None:  # Cover safe English default case.
        tracks = [parse_audio_report_track("English (eng)", 0), parse_audio_report_track("Brazilian Portuguese (por)", 1)]  # Build report tracks.
        self.assertEqual(select_default_audio_track(tracks)[0], 0)  # Assert unique English position selected.

    def test_multiple_english_candidates_are_ambiguous(self) -> None:  # Cover repeated English ambiguity.
        tracks = [parse_audio_report_track("English (eng)", 0), parse_audio_report_track("English (eng)", 1), parse_audio_report_track("Brazilian Portuguese (por)", 2)]  # Build ambiguous report tracks.
        self.assertIsNone(select_default_audio_track(tracks)[0])  # Assert no default target selected.

    def test_english_and_french_candidates_are_ambiguous(self) -> None:  # Cover cross-language ambiguity.
        tracks = [parse_audio_report_track("English (eng)", 0), parse_audio_report_track("French (fre)", 1), parse_audio_report_track("Brazilian Portuguese (por)", 2)]  # Build ambiguous original candidates.
        self.assertIsNone(select_default_audio_track(tracks)[0])  # Assert no default target selected.

    def test_unique_french_candidate_selected(self) -> None:  # Cover unique non-English original case.
        tracks = [parse_audio_report_track("French (fre)", 0), parse_audio_report_track("Brazilian Portuguese (por)", 1)]  # Build French plus PT-BR tracks.
        self.assertEqual(select_default_audio_track(tracks)[0], 0)  # Assert French selected.

    def test_multiple_french_candidates_are_ambiguous(self) -> None:  # Cover repeated French ambiguity.
        tracks = [parse_audio_report_track("French (fre)", 0), parse_audio_report_track("French (fre)", 1), parse_audio_report_track("Brazilian Portuguese (por)", 2)]  # Build ambiguous French tracks.
        self.assertIsNone(select_default_audio_track(tracks)[0])  # Assert no default target selected.

    def test_unresolved_existing_default_is_cleared_when_target_is_known(self) -> None:  # Cover two-default prevention.
        movie = MovieReportEntry(Path("report.json"), Path("."), Path("movie.mkv"), [parse_audio_report_track("English (eng)", 0), parse_audio_report_track("Unknown (Default)", 1)], [])  # Build report entry.
        streams = [StreamSnapshot(0, 0, 10, "aac", "audio", "eng", "en", "", False, False), StreamSnapshot(1, 1, 11, "aac", "audio", "", "", "", True, False)]  # Build current streams.
        summary = WorkflowSummary()  # Build summary.
        edits, default_position = plan_audio_metadata_edits(movie, streams, summary)  # Plan audio edits.
        default_edits = {edit.selector: edit.default_flag for edit in edits if edit.default_flag is not None}  # Collect default setters.
        self.assertEqual(default_position, 0)  # Assert English target selected.
        self.assertEqual(default_edits, {"track:=10": True, "track:=11": False})  # Assert old default clears.

    def test_portuguese_and_brazilian_portuguese_are_distinct(self) -> None:  # Cover Portuguese distinction.
        tracks = [parse_audio_report_track("Portuguese (por)", 0), parse_audio_report_track("Brazilian Portuguese (por)", 1)]  # Build Portuguese-family tracks.
        self.assertEqual(tracks[0].language, "Portuguese")  # Assert generic Portuguese remains distinct.
        self.assertEqual(tracks[1].language, "Brazilian Portuguese")  # Assert PT-BR remains distinct.
        self.assertEqual(select_default_audio_track(tracks)[0], 0)  # Assert Portuguese can be original candidate.

    def test_mixed_case_pt_br_aliases(self) -> None:  # Cover PT-BR alias variants.
        values = ["PT-BR", "Pt-Br", "pt-br", "PORTUGUÊS BRASIL", "Português Brasil", "português brasil"]  # Build alias cases.
        self.assertEqual([normalize_language_value(value) for value in values], ["Brazilian Portuguese"] * len(values))  # Assert all aliases normalize consistently.

    def test_unknown_audio_fails_safely(self) -> None:  # Cover malformed unknown value.
        track = parse_audio_report_track("Mystery Track", 0)  # Parse unknown row.
        self.assertEqual(track.language, "")  # Assert unknown language stays unresolved.

    def test_subtitle_name_uses_reference_convention(self) -> None:  # Cover subtitle canonical naming.
        track = parse_subtitle_report_track("Internal: por (subrip) - Forced Brazilian Portuguese", 0)  # Parse forced PT-BR subtitle.
        self.assertEqual(track.target_name, "Forced Brazilian Portuguese")  # Assert reference subtitle title convention.

    def test_subtitle_full_french_stays_canonical(self) -> None:  # Cover Full French naming.
        track = parse_subtitle_report_track("Internal: fre (subrip) - Full French", 0)  # Parse Full French subtitle.
        self.assertEqual(track.target_name, "Full French")  # Assert canonical Full French title.

    def test_forced_subtitle_flag_sets_forced_name_when_report_type_missing(self) -> None:  # Cover actual forced metadata fallback.
        movie = MovieReportEntry(Path("report.json"), Path("."), Path("movie.mkv"), [], [parse_subtitle_report_track("Internal: eng (subrip)", 0)])  # Build subtitle-only report entry.
        streams = [StreamSnapshot(0, 2, 12, "subrip", "subtitle", "eng", "en", "English", False, True)]  # Build forced current subtitle.
        summary = WorkflowSummary()  # Build summary.
        edits = plan_subtitle_metadata_edits(movie, streams, summary)  # Plan subtitle metadata edits.
        self.assertEqual(edits[0].new_name, "Forced English")  # Assert forced flag controls missing type.

    def test_external_subtitle_is_not_internal(self) -> None:  # Cover external subtitle skip.
        track = parse_subtitle_report_track("External: Movie Name.srt", 0)  # Parse external subtitle row.
        self.assertFalse(track.internal)  # Assert row is not container target.

    def test_progress_path_uses_report_input_root(self) -> None:  # Cover relative progress label.
        movie = MovieReportEntry(Path("report.json"), Path("F:/Movies"), Path("F:/Movies/Dual/Movie/Movie.mkv"), [], [])  # Build report-rooted movie entry.
        self.assertEqual(build_progress_media_path(movie), "Dual\\Movie\\Movie.mkv")  # Assert progress label is report-relative.


if __name__ == "__main__":  # Run tests when executed directly.
    unittest.main()  # Execute regression suite.
