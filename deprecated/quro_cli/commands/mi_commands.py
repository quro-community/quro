"""
MI-Path Training Commands - CLI plugin for MI-path training system

@module quro_cli.commands.mi_commands
@intent Provide CLI commands for MI-path analysis, training, and evaluation

Commands:
  - mi-analyze: Analyze reflection log and generate audit report
  - mi-extract: Extract training pairs from reflection log (Phase 2)
  - mi-generate: Generate MI training pairs from QRA2 chains + reflection log
  - mi-train: Train local Qwen3 model on MI-path prediction
  - mi-eval: Evaluate trained model on validation set
"""

import click
from pathlib import Path


# Plugin metadata for command indexing
METADATA = {
    'description': 'MI-Path Training System - Local model training for CQE optimization',
    'commands': {
        'mi-analyze': {
            'description': 'Analyze reflection log and generate audit report',
            'usage': 'quro mi-analyze [--output-dir .quro_context]',
            'implementation': 'quro_cli/commands/mi_commands.py:mi_analyze'
        },
        'mi-extract': {
            'description': 'Extract training pairs from reflection log (Phase 2)',
            'usage': 'quro mi-extract [--min-quality 0.6] [--output mi_training_pairs.jsonl] [--qra2]',
            'implementation': 'quro_cli/commands/mi_commands.py:mi_extract'
        },
        'mi-generate': {
            'description': 'Generate MI training pairs from QRA2 chains + reflection log',
            'usage': 'quro mi-generate [--workspace .] [--validation-ratio 0.2]',
            'implementation': 'quro_cli/commands/mi_commands.py:mi_generate'
        },
        'mi-train': {
            'description': 'Train local Qwen3 model on MI-path prediction',
            'usage': 'quro mi-train [--iters 100] [--batch-size 8]',
            'implementation': 'quro_cli/commands/mi_commands.py:mi_train'
        },
        'mi-eval': {
            'description': 'Evaluate trained model on validation set',
            'usage': 'quro mi-eval [--model-path .quro_context/mi_model.pt]',
            'implementation': 'quro_cli/commands/mi_commands.py:mi_eval'
        }
    }
}


def register(cli: click.Group):
    """Register MI-path commands with CLI"""
    cli.add_command(mi_analyze)
    cli.add_command(mi_extract)
    cli.add_command(mi_generate)
    cli.add_command(mi_train)
    cli.add_command(mi_eval)


@click.command('mi-analyze')
@click.option('--output-dir', type=click.Path(), default='.quro_context',
              help='Output directory for reports')
def mi_analyze(output_dir: str):
    """Analyze reflection log and generate audit report"""
    from quro_sovereign.mi_path_audit_logger import MIPathAuditLogger

    output_path = Path(output_dir)
    reflection_log_path = Path('.quro_context/cqe_reflections.jsonl')

    click.echo("📋 MI-Path Analysis")
    click.echo("="*60)

    if not reflection_log_path.exists():
        click.echo(f"❌ Reflection log not found: {reflection_log_path}", err=True)
        return

    # Generate audit logs
    logger = MIPathAuditLogger(reflection_log_path)

    click.echo("\n📝 Generating Markdown audit report...")
    md_path = output_path / 'mi_path_audit.md'
    logger.generate_markdown_report(md_path)

    click.echo("\n📦 Generating training candidates JSON...")
    json_path = output_path / 'training_candidates.json'
    logger.generate_training_candidates_json(json_path, min_quality=0.6)

    click.echo("\n✅ Analysis complete!")
    click.echo(f"\n📄 Review: {md_path}")
    click.echo(f"📊 Candidates: {json_path}")


@click.command('mi-extract')
@click.option('--min-quality', type=float, default=0.6,
              help='Minimum quality score for training pairs')
@click.option('--output', type=click.Path(), default='.quro_context/mi_training_pairs.jsonl',
              help='Output file for training pairs')
@click.option('--contrastive-ratio', type=float, default=0.3,
              help='Ratio of negative examples (default 0.3)')
@click.option('--qra2', is_flag=True, default=False,
              help='Include QRA2-verified pairs from chains/index.jsonl')
@click.option('--workspace', type=click.Path(), default='.',
              help='Project root directory')
def mi_extract(min_quality: float, output: str, contrastive_ratio: float,
               qra2: bool, workspace: str):
    """Extract training pairs from reflection log (Phase 2 - Automated).

    Use --qra2 to include QRA2-verified pairs from chains/index.jsonl in addition
    to reflection-log pairs. This activates MIPathDatasetGenerator which handles
    both QRA2 and QRAv1 sources.
    """
    output_path = Path(output)
    workspace_path = Path(workspace)

    if qra2:
        from quro_sovereign.mi_path_trainer import MIPathDatasetGenerator

        click.echo("MI-Path Training Pair Extraction (QRA2 + QRAv1)")
        click.echo("=" * 60)

        gen = MIPathDatasetGenerator(workspace_path)
        train_pairs, val_pairs = gen.generate_training_set(
            train_ratio=1.0 - contrastive_ratio,
        )

        click.echo(f"\nExtraction complete!")
        click.echo(f"  Training pairs: {len(train_pairs)}")
        click.echo(f"  Validation pairs: {len(val_pairs)}")

        # Generator writes to its own default paths
        gen_train = workspace_path / ".quro_context" / "mi_training_pairs.jsonl"
        gen_val = workspace_path / ".quro_context" / "mi_validation_pairs.jsonl"

        click.echo(f"\nSaved to:")
        click.echo(f"  Train: {gen_train}")
        click.echo(f"  Val: {gen_val}")
    else:
        from quro_sovereign.mi_path_extractor import MIPathExtractor

        click.echo("MI-Path Training Pair Extraction (Reflection Log)")
        click.echo("=" * 60)

        reflection_log_path = workspace_path / '.quro_context/cqe_reflections.jsonl'
        index_path = workspace_path / '.quro_context/cqe_index.db'

        if not reflection_log_path.exists():
            click.echo(f"Reflection log not found: {reflection_log_path}", err=True)
            return

        if not index_path.exists():
            click.echo(f"CQE index not found: {index_path}", err=True)
            return

        extractor = MIPathExtractor(
            reflection_log_path=reflection_log_path,
            index_path=index_path
        )

        click.echo(f"Extracting training pairs (min_quality={min_quality})...")
        train_pairs, val_pairs = extractor.extract_all(
            min_quality=min_quality,
            contrastive_ratio=contrastive_ratio
        )

        click.echo(f"\nExtraction complete!")
        click.echo(f"  Training pairs: {len(train_pairs)}")
        click.echo(f"  Validation pairs: {len(val_pairs)}")

        extractor.save_jsonl(train_pairs, output_path)
        val_output = output_path.parent / f"{output_path.stem}_val.jsonl"
        extractor.save_jsonl(val_pairs, val_output)

        click.echo(f"\nSaved to:")
        click.echo(f"  Train: {output_path}")
        click.echo(f"  Val: {val_output}")


@click.command('mi-generate')
@click.option('--workspace', type=click.Path(), default='.',
              help='Project root directory')
@click.option('--validation-ratio', type=float, default=0.2,
              help='Validation split ratio (default 0.2)')
def mi_generate(workspace: str, validation_ratio: float):
    """Generate MI training pairs from QRA2 chains + reflection log.

    Reads .quro_context/chains/index.jsonl for QRA2-verified pairs and
    cqe_reflections.jsonl for QRAv1 pairs. Outputs mi_training_pairs.jsonl.
    """
    from quro_sovereign.mi_path_trainer import MIPathDatasetGenerator

    workspace_path = Path(workspace)

    click.echo("MI Training Pair Generation (QRA2 + QRAv1)")
    click.echo("=" * 60)

    gen = MIPathDatasetGenerator(workspace_path)
    train_pairs, val_pairs = gen.generate_training_set(
        train_ratio=1.0 - validation_ratio,
    )

    click.echo(f"\nGeneration complete!")
    click.echo(f"  Training pairs: {len(train_pairs)}")
    click.echo(f"  Validation pairs: {len(val_pairs)}")

    train_path = workspace_path / ".quro_context" / "mi_training_pairs.jsonl"
    val_path = workspace_path / ".quro_context" / "mi_validation_pairs.jsonl"
    click.echo(f"\nSaved to:")
    click.echo(f"  Train: {train_path}")
    click.echo(f"  Val: {val_path}")
    click.echo(f"\nNext: quro mi-train")


@click.command('mi-train')
@click.option('--iters', type=int, default=100, help='Number of training iterations')
@click.option('--batch-size', type=int, default=4, help='Batch size (MLX default: 4)')
@click.option('--learning-rate', type=float, default=1e-5, help='Learning rate')
@click.option('--base-model', default='.models/Qwen/Qwen3-0.6B-MLX-4bit',
              help='Base MLX model path')
@click.option('--lora-rank', type=int, default=8, help='LoRA rank')
@click.option('--lora-alpha', type=int, default=16, help='LoRA alpha')
@click.option('--train-data', type=click.Path(exists=True),
              default='.quro_context/mi_training_pairs.jsonl',
              help='Training data path')
@click.option('--val-data', type=click.Path(exists=True),
              default='.quro_context/mi_validation_pairs.jsonl',
              help='Validation data path')
def mi_train(iters: int, batch_size: int, learning_rate: float, base_model: str,
             lora_rank: int, lora_alpha: int, train_data: str, val_data: str):
    """Train local Qwen3 model on MI-path prediction (Phase 3 - MLX + LoRA)"""
    from quro_sovereign.mi_model_trainer import MIModelTrainer
    import logging

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    click.echo("🚀 MI-Path Model Training (Phase 3 - MLX + LoRA)")
    click.echo("="*60)

    train_path = Path(train_data)
    val_path = Path(val_data)

    if not train_path.exists():
        click.echo(f"\n❌ Training data not found: {train_path}", err=True)
        click.echo("Run 'quro mi-extract' first to generate training data.")
        return

    if not val_path.exists():
        click.echo(f"\n❌ Validation data not found: {val_path}", err=True)
        click.echo("Run 'quro mi-extract' first to generate validation data.")
        return

    click.echo(f"\n📊 Configuration:")
    click.echo(f"  Base Model: {base_model}")
    click.echo(f"  Training Method: LoRA (Low-Rank Adaptation)")
    click.echo(f"  Iterations: {iters}")
    click.echo(f"  Batch size: {batch_size}")
    click.echo(f"  Learning rate: {learning_rate}")
    click.echo(f"  LoRA rank: {lora_rank}")
    click.echo(f"  LoRA alpha: {lora_alpha}")
    click.echo(f"  Training data: {train_path}")
    click.echo(f"  Validation data: {val_path}")

    try:
        # Initialize MLX trainer
        click.echo("\n🔧 Initializing MLX trainer...")
        trainer = MIModelTrainer(
            base_model_path=base_model,
            output_dir=Path('.quro_context/mi_model')
        )

        # Train model with LoRA
        click.echo("\n🚀 Starting LoRA fine-tuning...")
        metrics = trainer.train(
            train_jsonl=train_path,
            val_jsonl=val_path,
            iters=iters,
            batch_size=batch_size,
            learning_rate=learning_rate,
            lora_rank=lora_rank,
            lora_alpha=lora_alpha
        )

        click.echo("\n✅ Training complete!")
        click.echo(f"\n📊 Final Metrics:")
        click.echo(f"  Validation Accuracy: {metrics['eval_results']['accuracy']:.4f}")
        click.echo(f"  Validation Loss: {metrics['eval_results']['loss']:.4f}")

        click.echo(f"\n💾 LoRA adapters saved to: .quro_context/mi_model/adapters")
        click.echo(f"📈 Metrics saved to: .quro_context/mi_model/training_metrics.json")
        click.echo(f"\n💡 Tip: Use these adapters with CQELocalModel for inference")

    except Exception as e:
        click.echo(f"\n❌ Training failed: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise


@click.command('mi-eval')
@click.option('--adapter-path', type=click.Path(exists=True),
              default='.quro_context/mi_model/adapters',
              help='Path to LoRA adapters directory')
@click.option('--base-model', default='.models/Qwen/Qwen3-0.6B-MLX-4bit',
              help='Base MLX model path')
@click.option('--val-data', type=click.Path(exists=True),
              default='.quro_context/mi_validation_pairs.jsonl',
              help='Validation data path')
@click.option('--output', type=click.Path(),
              default='.quro_context/mi_model/evaluation_report.json',
              help='Output path for evaluation report')
def mi_eval(adapter_path: str, base_model: str, val_data: str, output: str):
    """Evaluate trained model on validation set (Phase 4 - MLX)"""
    from quro_sovereign.mi_model_trainer import MIModelTrainer, MIPathDataset
    import json
    import logging

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    click.echo("📊 MI-Path Model Evaluation (Phase 4 - MLX)")
    click.echo("="*60)

    adapter_path = Path(adapter_path)
    val_path = Path(val_data)
    output_path = Path(output)

    if not adapter_path.exists():
        click.echo(f"\n❌ LoRA adapters not found: {adapter_path}", err=True)
        click.echo("Run 'quro mi-train' first to train the model.")
        return

    if not val_path.exists():
        click.echo(f"\n❌ Validation data not found: {val_path}", err=True)
        return

    try:
        # Load trained model with adapters
        click.echo(f"\n🔧 Loading model with LoRA adapters: {adapter_path}")
        trainer = MIModelTrainer(base_model_path=base_model)
        trainer.load_trained_model(adapter_path)

        # Load validation dataset
        click.echo(f"📦 Loading validation data: {val_path}")
        val_dataset = MIPathDataset(val_path)

        # Evaluate
        click.echo(f"\n🔍 Evaluating on {len(val_dataset)} samples...")
        click.echo("(Sampling 100 examples for evaluation)")

        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler
        import numpy as np

        correct = 0
        total = 0
        predictions = []
        labels = []

        sampler = make_sampler(temp=0.1)

        # Sample 100 examples
        eval_size = min(100, len(val_dataset))
        indices = np.random.choice(len(val_dataset), eval_size, replace=False)

        for i, idx in enumerate(indices):
            sample = val_dataset[int(idx)]

            # Generate prediction
            prompt = trainer.tokenizer.apply_chat_template([
                {"role": "user", "content": f"{sample['text']}\nLabel:"}
            ])

            response = generate(
                trainer.model,
                trainer.tokenizer,
                prompt=prompt,
                max_tokens=10,
                sampler=sampler
            )

            # Parse prediction
            pred = 1 if "positive" in response.lower() else 0
            label = sample['label']

            predictions.append(pred)
            labels.append(label)

            if pred == label:
                correct += 1
            total += 1

            if (i + 1) % 10 == 0:
                click.echo(f"  Processed {i+1}/{eval_size} samples...")

        # Calculate metrics
        accuracy = correct / total

        # Precision, recall, F1
        tp = sum((p == 1 and l == 1) for p, l in zip(predictions, labels))
        fp = sum((p == 1 and l == 0) for p, l in zip(predictions, labels))
        fn = sum((p == 0 and l == 1) for p, l in zip(predictions, labels))
        tn = sum((p == 0 and l == 0) for p, l in zip(predictions, labels))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        # Create evaluation report
        report = {
            'adapter_path': str(adapter_path),
            'base_model': base_model,
            'validation_data': str(val_path),
            'eval_samples': total,
            'metrics': {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1': f1
            },
            'confusion_matrix': {
                'true_positive': tp,
                'false_positive': fp,
                'false_negative': fn,
                'true_negative': tn
            }
        }

        # Save report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        # Display results
        click.echo("\n✅ Evaluation complete!")
        click.echo(f"\n📊 Metrics:")
        click.echo(f"  Accuracy: {accuracy:.4f}")
        click.echo(f"  Precision: {precision:.4f}")
        click.echo(f"  Recall: {recall:.4f}")
        click.echo(f"  F1 Score: {f1:.4f}")

        click.echo(f"\n📈 Confusion Matrix:")
        click.echo(f"  True Positive: {tp}")
        click.echo(f"  False Positive: {fp}")
        click.echo(f"  False Negative: {fn}")
        click.echo(f"  True Negative: {tn}")

        click.echo(f"\n💾 Report saved to: {output_path}")

    except Exception as e:
        click.echo(f"\n❌ Evaluation failed: {e}", err=True)
        import traceback
        traceback.print_exc()
        raise
