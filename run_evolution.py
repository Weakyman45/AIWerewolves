#!/usr/bin/env python3
import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.evolution import EvolutionController


def parse_args():
    parser = argparse.ArgumentParser(description="Run the Werewolve self-evolution loop.")
    parser.add_argument("--iterations", type=int, default=1, help="Number of evolution iterations to run.")
    parser.add_argument("--train-games", type=int, default=1, help="Training games per iteration.")
    parser.add_argument("--ab-games", type=int, default=1, help="A/B test games per iteration.")
    parser.add_argument("--win-rate-threshold", type=float, default=0.05, help="Minimum win-rate improvement needed for acceptance.")
    parser.add_argument("--skip-ab", action="store_true", help="Create a candidate version without running A/B validation.")
    parser.add_argument("--dry-run", action="store_true", help="Skip live training games and A/B; only analyze logs and create a candidate version.")
    parser.add_argument("--initial-version", default=None, help="Strategy version to start from.")
    return parser.parse_args()


async def main():
    args = parse_args()

    print("=" * 80)
    print("AI 狼人杀 - 启动自进化循环")
    print("=" * 80)
    
    controller = EvolutionController(
        initial_version=args.initial_version,
        num_games_per_iteration=args.train_games,
        ab_games=args.ab_games,
        win_rate_threshold=args.win_rate_threshold,
        skip_ab=args.skip_ab,
        dry_run=args.dry_run,
    )
    
    print("\n初始化系统...")
    controller.initialize()
    print(f"当前版本: {controller.current_version}")
    
    def progress_callback(iteration, total, phase, result=None):
        if phase == "starting":
            print(f"\n--- 迭代 {iteration}/{total} 开始 ---")
        elif phase == "completed":
            print(f"\n--- 迭代 {iteration}/{total} 完成 ---")
            if result:
                print(f"接受新版本: {result.get('accepted', False)}")
    
    print("\n" + "=" * 80)
    print(f"开始进化循环（{args.iterations}次迭代）...")
    print(f"训练局数/迭代: {args.train_games}")
    print(f"A/B局数/迭代: {args.ab_games}")
    print(f"跳过A/B: {args.skip_ab}")
    print(f"dry-run: {args.dry_run}")
    print("=" * 80)
    
    try:
        result = await controller.start_evolution(
            max_iterations=args.iterations,
            progress_callback=progress_callback
        )
        
        print("\n" + "=" * 80)
        print("进化完成！")
        print("=" * 80)
        
        print(f"\n总迭代次数: {result.get('total_iterations', 0)}")
        print(f"最终版本: {result.get('final_version', 'unknown')}")
        
        history = result.get('history', [])
        print(f"\n进化历史:")
        for i, item in enumerate(history):
            print(f"  迭代 {i+1}: {'✓' if item.get('result', {}).get('accepted') else '✗'}")
        
    except KeyboardInterrupt:
        print("\n\n用户中断，停止进化")
        controller.stop_evolution()
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
