import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqlite3/sqlite3.dart';
import 'package:url_launcher/url_launcher.dart';

const buildStamp = String.fromEnvironment('BUILD_STAMP', defaultValue: 'unstamped');

void main() => runApp(const HelloApp());

class HelloApp extends StatelessWidget {
  const HelloApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Hello Omarchy',
        theme: ThemeData(colorSchemeSeed: Colors.teal),
        home: const HomePage(),
      );
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final lines = <String>[];

  @override
  void initState() {
    super.initState();
    _probe();
  }

  Future<void> _probe() async {
    final found = <String>[];
    try {
      final db = sqlite3.openInMemory();
      final rows = db.select('select sqlite_version() as v, 6 * 7 as answer');
      found.add('sqlite3 (FFI, native asset): ${rows.first['v']}, 6*7=${rows.first['answer']}');
      db.dispose();
    } catch (e) {
      found.add('sqlite3 FAILED: $e');
    }
    try {
      final prefs = await SharedPreferences.getInstance();
      final launches = (prefs.getInt('launches') ?? 0) + 1;
      await prefs.setInt('launches', launches);
      found.add('shared_preferences (plugin channel): launch #$launches');
    } catch (e) {
      found.add('shared_preferences FAILED: $e');
    }
    try {
      final dir = await getApplicationDocumentsDirectory();
      found.add('path_provider: …/${dir.path.split('/').last}');
    } catch (e) {
      found.add('path_provider FAILED: $e');
    }
    try {
      final ok = await canLaunchUrl(Uri.parse('https://flutter.dev'));
      found.add('url_launcher: canLaunchUrl=$ok');
    } catch (e) {
      found.add('url_launcher FAILED: $e');
    }
    setState(() => lines.addAll(found));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Flutter on iOS, built on Linux')),
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.rocket_launch, size: 48),
              const SizedBox(height: 12),
              Text('Build stamp: $buildStamp', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 16),
              for (final line in lines) Padding(padding: const EdgeInsets.only(bottom: 8), child: Text(line)),
            ],
          ),
        ),
      );
}
