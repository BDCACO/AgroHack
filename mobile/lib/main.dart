import 'package:flutter/material.dart';

import 'app.dart';
import 'core/api/cliente_api.dart';

void main() {
  runApp(CampoCertoApp(api: ClienteApi()));
}
