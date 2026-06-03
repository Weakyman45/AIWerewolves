#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.evolution import EvolutionController


async def main():
    print("=" * 80)
    print("AI 狼人杀 - 启动自进化循环")
    print("=" * 80)
    
    controller = EvolutionController(
        num_games_per_iteration=2,
        win_rate_threshold=0.05
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
    print("开始进化循环（3次迭代）...")
    print("=" * 80)
    
    try:
        result = await controller.start_evolution(
            max_iterations=3,
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
